// Coherent SFDR / HD2 / HD3 (one tone) and IMD3 (two tones) of a DDS/DAC record.
// Cross-check of sfdr.py: same method, same numbers.
//
//   cargo run --release -- --file run.bin --m 2457                 # single tone
//   cargo run --release -- --file run.bin --m 2455 --m2 2457       # two tones -> IMD3
//
// Tones must sit on FFT bins (M odd, NFFT = 2^LOG2N) -> rectangular window, no leakage.
// fOUT = M / NFFT * fDAC.  Levels in dBFS relative to 2^bits (DW-1+FRAC = 19), spurs in dBc.

use clap::Parser;
use rustfft::{num_complex::Complex, FftPlanner};
use std::fs;

#[derive(Parser, Debug)]
#[command(version, about)]
struct Args {
    #[arg(short, long)]
    file: String,
    /// bin of tone 1 (odd)
    #[arg(long)]
    m: usize,
    /// bin of tone 2 -> two-tone IMD3
    #[arg(long)]
    m2: Option<usize>,
    /// full scale = 2^bits
    #[arg(long, default_value_t = 19)]
    bits: u32,
    /// int32 (File Sink sizeof_int) or float32
    #[arg(long, default_value = "int32")]
    dtype: String,
    #[arg(long, default_value_t = 1000)]
    skip: usize,
    #[arg(long, default_value_t = 32768)]
    nfft: usize,
    /// MHz, only for labels
    #[arg(long, default_value_t = 12000.0)]
    fdac: f64,
}

fn read(path: &str, dtype: &str) -> Vec<f64> {
    let b = fs::read(path).unwrap_or_else(|e| panic!("cannot read {path}: {e}"));
    b.chunks_exact(4)
        .map(|c| {
            let a: [u8; 4] = c.try_into().unwrap();
            match dtype {
                "int32" => i32::from_le_bytes(a) as f64,
                "float32" => f32::from_le_bytes(a) as f64,
                _ => panic!("dtype must be int32 or float32"),
            }
        })
        .collect()
}

fn fold(b: i64, n: i64) -> usize {
    let b = b.rem_euclid(n);
    (if b > n / 2 { n - b } else { b }) as usize
}

fn main() {
    let a = Args::parse();
    let x = read(&a.file, &a.dtype);
    if x.len() < a.skip + a.nfft {
        eprintln!("{}: {} samples, need {}", a.file, x.len(), a.skip + a.nfft);
        std::process::exit(1);
    }
    let n = a.nfft;
    let fs_amp = 2f64.powi(a.bits as i32);

    let mut buf: Vec<Complex<f64>> =
        x[a.skip..a.skip + n].iter().map(|&v| Complex::new(v, 0.0)).collect();
    FftPlanner::<f64>::new().plan_fft_forward(n).process(&mut buf);
    let d: Vec<f64> = (0..=n / 2)
        .map(|k| {
            let mut amp = buf[k].norm() / (n as f64 / 2.0);
            if k == 0 { amp /= 2.0; }
            20.0 * (amp / fs_amp).max(1e-20).log10()
        })
        .collect();

    let ni = n as i64;
    let m1 = a.m as i64;
    let worst = |exclude: &[usize]| -> (usize, f64) {
        (1..d.len())
            .filter(|k| !exclude.contains(k))
            .map(|k| (k, d[k]))
            .fold((0, f64::NEG_INFINITY), |acc, c| if c.1 > acc.1 { c } else { acc })
    };

    match a.m2 {
        None => {
            if a.m % 2 == 0 { println!("WARNING: M = {} is even", a.m); }
            let c = d[a.m];
            let (sb, sv) = worst(&[a.m]);
            println!("single tone M={} fOUT={:.1} MHz", a.m, a.m as f64 / n as f64 * a.fdac);
            println!("carrier {:.2} dBFS | SFDR {:.2} dBc (bin {})", c, c - sv, sb);
            for k in 2..=5 {
                println!("  HD{} {:+.2} dBc", k, d[fold(k * m1, ni)] - c);
            }
        }
        Some(m2) => {
            let m2i = m2 as i64;
            let r = d[a.m].max(d[m2]);
            let lo = d[fold(2 * m1 - m2i, ni)] - r;
            let hi = d[fold(2 * m2i - m1, ni)] - r;
            let (sb, sv) = worst(&[a.m, m2]);
            println!("two tones M1={} M2={} fc={:.1} MHz spacing {:.3} MHz", a.m, m2,
                     (a.m + m2) as f64 / 2.0 / n as f64 * a.fdac, (m2 - a.m) as f64 / n as f64 * a.fdac);
            println!("tones {:.2} / {:.2} dBFS", d[a.m], d[m2]);
            println!("IMD3 2f1-f2 {:+.2} dBc | 2f2-f1 {:+.2} dBc | worst {:+.2} dBc", lo, hi, lo.max(hi));
            println!("worst spur excluding tones {:.2} dBc below, bin {}", r - sv, sb);
        }
    }
}
