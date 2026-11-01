# Pemindai sinyal pra-rilis

Semua berjalan di cloud gratis: GitHub Actions (pengumpul, tiap 3 jam) + GitHub Pages (dashboard). Tidak ada yang berjalan di laptop.

## Pasang (±10 menit)
1. Buat akun GitHub, repo baru (public agar Pages & Actions gratis tanpa batas), unggah semua isi folder ini.
2. Settings > Pages > Source: branch `main`, folder `/docs`.
3. Settings > Actions > General > Workflow permissions: Read and write.
4. Tab Actions > "Pindai" > Run workflow. Setelah selesai, buka `https://<user>.github.io/<repo>/`.
5. Perluas `data/emiten.csv` (kode, nama, alias) ke seluruh emiten yang diteliti.

## Mencatat hasil
Tambah baris di `data/outcomes.csv` lewat editor web GitHub: `ticker,t0,status,note` (status: terbukti / dibantah / kedaluwarsa).
Lead time dan CAR terhitung otomatis pada run berikutnya.

## Batasan
- RSS hanya memberi judul dan cuplikan, bukan teks penuh; deteksi frasa terbatas pada itu.
- Cakupan Google News 3 hari terakhir tiap run; arsip menumpuk di `docs/data/signals.json`.
- UMA BEI, jawaban emiten di IDX, dan SIPP belum otomatis (situs memblokir IP datacenter / butuh format khusus); catat manual lewat outcomes.csv.
