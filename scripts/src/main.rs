use clap::Parser;
use rustfft::{num_complex::Complex, FftPlanner};
use std::fs::File;
use std::io::{BufReader, Read};

#[derive(Parser, Debug)]
#[command(version, about)]
struct Args {
    #[arg(short, long)]
    file: String,

    #[arg(long, default_value_t = 32000.0)]
    fs: f64,

    #[arg(long)]
    f1: f64,

    #[arg(long)]
    f2: f64,

    #[arg(long, default_value_t = 5)]
    tol_bins: usize,
}

fn read_f32_file(path: &str) -> std::io::Result<Vec<f32>> {
    let f = File::open(path)?;
    let mut reader = BufReader::new(f);
    let mut buf = Vec::new();
    reader.read_to_end(&mut buf)?;

    let n = buf.len() / 4;
    let mut samples = Vec::with_capacity(n);
    for chunk in buf.chunks_exact(4) {
        let bytes: [u8; 4] = chunk.try_into().unwrap();
        samples.push(f32::from_le_bytes(bytes));
    }
    Ok(samples)
}

fn blackman_window(n: usize) -> Vec<f64> {
    (0..n)
        .map(|i| {
            let x = i as f64 / (n - 1) as f64;
            0.42 - 0.5 * (2.0 * std::f64::consts::PI * x).cos()
                + 0.08 * (4.0 * std::f64::consts::PI * x).cos()
        })
        .collect()
}

fn peak_near(mag_db: &[f64], freqs: &[f64], target: f64, tol_bins: usize) -> (f64, f64) {
    let center = freqs
        .iter()
        .enumerate()
        .min_by(|a, b| {
            (a.1 - target)
                .abs()
                .partial_cmp(&(b.1 - target).abs())
                .unwrap()
        })
        .map(|(i, _)| i)
        .unwrap_or(0);

    let lo = center.saturating_sub(tol_bins);
    let hi = (center + tol_bins).min(mag_db.len() - 1);

    let (best_idx, best_val) = (lo..=hi)
        .map(|i| (i, mag_db[i]))
        .fold((lo, mag_db[lo]), |acc, cur| if cur.1 > acc.1 { cur } else { acc });

    (freqs[best_idx], best_val)
}

fn main() {
    let args = Args::parse();

    let samples = read_f32_file(&args.file).expect("не удалось прочитать файл");
    let n = samples.len();
    if n == 0 {
        eprintln!("Файл пуст");
        std::process::exit(1);
    }

    println!("Прочитано отсчётов: {}", n);

    let window = blackman_window(n);
    let mut buffer: Vec<Complex<f64>> = samples
        .iter()
        .zip(window.iter())
        .map(|(&s, &w)| Complex::new(s as f64 * w, 0.0))
        .collect();

    let mut planner = FftPlanner::<f64>::new();
    let fft = planner.plan_fft_forward(n);
    fft.process(&mut buffer);

    let half = n / 2;
    let mag_db: Vec<f64> = buffer[..half]
        .iter()
        .map(|c| 20.0 * (c.norm() + 1e-12).log10())
        .collect();
    let freqs: Vec<f64> = (0..half).map(|i| i as f64 * args.fs / n as f64).collect();

    let (f1_meas, p1) = peak_near(&mag_db, &freqs, args.f1, args.tol_bins);
    let (f2_meas, p2) = peak_near(&mag_db, &freqs, args.f2, args.tol_bins);

    let imd3_lo_target = 2.0 * args.f1 - args.f2; //нижний продукт интермодуляции
    let imd3_hi_target = 2.0 * args.f2 - args.f1; //верхний продукт интремодуляции
    
    let (f_imd3_lo, p_imd3_lo) = peak_near(&mag_db, &freqs, imd3_lo_target, args.tol_bins);
    let (f_imd3_hi, p_imd3_hi) = peak_near(&mag_db, &freqs, imd3_hi_target, args.tol_bins);

    let ref_level = p1.max(p2);

    println!("--- Основные тона ---");
    println!("f1: цель {:.1} Гц, найден {:.1} Гц, {:.2} дБ", args.f1, f1_meas, p1);
    println!("f2: цель {:.1} Гц, найден {:.1} Гц, {:.2} дБ", args.f2, f2_meas, p2);

    println!("--- IMD3 ---");
    println!(
        "2f1-f2: цель {:.1} Гц, найден {:.1} Гц, {:.2} дБ ({:.2} дБс)",
        imd3_lo_target, f_imd3_lo, p_imd3_lo, p_imd3_lo - ref_level
    );
    println!(
        "2f2-f1: цель {:.1} Гц, найден {:.1} Гц, {:.2} дБ ({:.2} дБс)",
        imd3_hi_target, f_imd3_hi, p_imd3_hi, p_imd3_hi - ref_level
    );

    let worst = (p_imd3_lo - ref_level).max(p_imd3_hi - ref_level);
    println!("--- Итог ---");
    println!("IMD3 (худший случай): {:.2} дБс", worst);
}
