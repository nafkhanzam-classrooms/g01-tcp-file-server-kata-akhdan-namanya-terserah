[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/mRmkZGKe)
# Network Programming - Assignment G01

## Anggota Kelompok
| Nama           | NRP        | Kelas     |
| ---            | ---        | ----------|
| Ahmad Satrio Arrohman | 5025241061 | Pemrograman Jaringan - D |
| Muhammad Akhdan Alwaafy | 5025241223 | Pemrograman Jaringan - D |

## Link Youtube (Unlisted)
Link ditaruh di bawah ini
```

```

## Penjelasan Program

### 1. Fungsi Komunikasi Inti (Sama pada Semua Server)

Sebelum membahas perbedaan arsitekturnya, semua server (dan juga *client*) berbagi fungsi dasar yang sama untuk berinteraksi:

* **`send_msg` & `recv_msg`**: Menggunakan pendekatan *Length-Prefixed Framing*. Setiap kali mengirim pesan teks, kode akan membungkus panjang pesan tersebut dalam 4-byte *header* menggunakan modul `struct` (`>I` untuk *big-endian unsigned integer*). Saat menerima, program akan membaca 4 byte pertama dulu untuk mengetahui berapa banyak data yang harus diterima selanjutnya.
* **`send_file_chunked` & `recv_file_chunked`**: Untuk transfer file, data tidak dikirim sekaligus agar tidak membuat RAM penuh (terutama untuk file besar). File dibaca dan dikirim dalam potongan kecil (*chunks*), misalnya 4096 atau 8192 byte. Transfer file diakhiri dengan *sentinel value* (header dengan panjang `0`) untuk memberi tahu penerima bahwa file sudah selesai dikirim.
* **Perintah yang Didukung**: `/list` (melihat isi folder `storage`), `/download` (mengunduh file dari server), dan `/upload` (mengunggah file ke server).

---

### 2. Arsitektur Penanganan Client (Perbedaan Keempat Server)

#### A. `server-sync.py` (Synchronous / Blocking)
Ini adalah bentuk server yang paling dasar dan sederhana.

* **Cara Kerja**: Server berjalan secara berurutan (*sequential*). Saat satu *client* terhubung, server akan masuk ke dalam *loop* untuk melayani *client* tersebut sampai ia memutuskan koneksi (terputus).
* **Kekurangan Utama**: Bersifat *blocking*. Jika ada *client* kedua yang mencoba terhubung saat server sedang melayani *client* pertama, *client* kedua harus mengantre dan tidak akan dilayani sampai *client* pertama selesai. Server ini tidak cocok untuk banyak pengguna secara bersamaan.

#### B. `server-thread.py` (Multi-Threading)
Server ini memecahkan masalah antrean pada `server-sync` dengan memanfaatkan *thread*.

* **Cara Kerja**: Setiap kali ada *client* baru yang terhubung (`self.server.accept()`), server akan membuat sebuah *Thread* baru (menggunakan `class Client(threading.Thread)`). Setiap *thread* berjalan secara independen untuk melayani *client*-nya masing-masing.
* **Kelebihan & Kekurangan**: Sangat mudah dipahami dan bisa menangani banyak *client* secara bersamaan (konkuren). Namun, membuat banyak *thread* memakan cukup banyak memori (RAM) dan pemrosesan CPU. Jika ada ribuan *client*, server ini bisa menjadi sangat berat. Terdapat juga penggunaan `threading.Lock()` untuk mencegah *race condition* saat mengakses daftar `all_clients`.

#### C. `server-select.py` (I/O Multiplexing dengan `select()`)
Server ini menggunakan pendekatan *asynchronous* (non-blocking) dan berjalan hanya dengan **satu thread**.

* **Cara Kerja**: Menggunakan fungsi bawaan sistem operasi `select.select()`. Server mendaftarkan semua *socket* (baik *socket* server utama maupun *socket* dari masing-masing *client*) ke dalam sebuah daftar. `select` akan memantau daftar tersebut dan hanya akan "membangunkan" program jika ada *socket* yang sudah siap dibaca (misalnya ada pesan masuk atau ada *client* baru).
* **Kelebihan & Kekurangan**: Jauh lebih hemat sumber daya dibandingkan *multi-threading* karena hanya butuh satu *thread* untuk menangani banyak *client*. Namun, fungsi `select()` biasa memiliki batas maksimal *file descriptor* yang bisa dipantau (biasanya sekitar 1024), sehingga kurang cocok untuk skala masif.

#### D. `server-poll.py` (I/O Multiplexing dengan `poll()`)
Ini adalah versi yang lebih modern dan skalabel dari `server-select.py`.

* **Cara Kerja**: Menggunakan `select.poll()`. Konsepnya mirip dengan `select`, tetapi menggunakan sistem pendaftaran *event-driven*. Setiap *socket* didaftarkan bersama dengan jenis *event* yang ingin dipantau (misal: `POLLIN` untuk data masuk, `POLLOUT` untuk socket yang siap dikirimi data).
* **Kelebihan & Kekurangan**: Sangat efisien dan lebih cepat daripada `select()` biasa karena tidak perlu melakukan iterasi pada seluruh daftar *socket* setiap kali ada pengecekan, dan tidak memiliki batasan ketat jumlah 1024 koneksi. Ini adalah cara yang umum digunakan di sistem berbasis Linux/UNIX untuk server berkinerja tinggi.

---

### 3. Penjelasan `client.py`

File ini adalah antarmuka interaktif yang menghubungkan pengguna dengan server mana pun yang sedang dijalankan.

* **Multiplexing Input**: *Client* ini cukup pintar karena menggunakan `select.select()` untuk memantau dua hal sekaligus secara bersamaan:
    1.  `client` (*socket* dari server): Memantau jika ada pesan masuk atau file (*broadcast*, balasan, dll).
    2.  `sys.stdin` (*keyboard input*): Memantau jika pengguna mengetikkan sesuatu di terminal.
* **Cara Kerja**: Berkat penggunaan `select` di sisi *client*, kamu bisa menerima pesan *broadcast* dari pengguna lain *bahkan ketika* kamu sedang asyik mengetik di terminal, tanpa membuat programnya membeku (*freeze*). File yang diunduh akan otomatis disimpan di folder `client_storage`.

## Screenshot Hasil
