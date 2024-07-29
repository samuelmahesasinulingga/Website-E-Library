# Mengimpor modul Flask untuk membuat aplikasi web
from flask import Flask, render_template, request, redirect, url_for, session, flash

# Mengimpor modul Flask-Mysqldb untuk integrasi dengan MySQL
from flask_mysqldb import MySQL, MySQLdb

# Mengimpor modul bcrypt untuk hashing password
import bcrypt

# Mengimpor modul datetime untuk mengelola tanggal dan waktu
from datetime import datetime, timedelta

# Inisialisasi aplikasi Flask
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Kunci rahasia untuk sesi

# Konfigurasi untuk integrasi ke MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'perpustakaan'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
mysql = MySQL(app)

@app.route('/')
def index():
    # Halaman utama, mengarahkan pengguna ke halaman login jika belum login
    if 'email' in session:
        return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Halaman login
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        curl = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        curl.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = curl.fetchone()
        curl.close()

        # Verifikasi email dan password
        if user and bcrypt.checkpw(password, user['password'].encode('utf-8')):
            session['name'] = user['name']
            session['email'] = user['email']
            return redirect(url_for('home'))
        else:
            flash("Gagal, Email dan Password Tidak Cocok")
            return redirect(url_for('login'))
    return render_template("login.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Halaman registrasi
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        hash_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, hash_password))
        mysql.connection.commit()
        cur.close()

        session['name'] = name
        session['email'] = email
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/home')
def home():
    # Halaman utama setelah login
    if 'email' in session:
        return render_template('home.html')
    return redirect(url_for('login'))

class Perpustakaan:
    @staticmethod
    def pinjam_buku(judul, nama, nim, tanggal_pinjam):
        # Fungsi untuk meminjam buku
        cur = None
        try:
            if not tanggal_pinjam:
                flash("Tanggal pinjam tidak valid.", "error")
                return

            tanggal_pinjam_obj = datetime.strptime(tanggal_pinjam, "%Y-%m-%d")
            tanggal_batas_pengembalian = tanggal_pinjam_obj + timedelta(days=7)

            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM buku WHERE judul = %s AND status = 'tersedia'", (judul,))
            buku = cur.fetchone()

            if buku:
                cur.execute("""
                    UPDATE buku
                    SET status = %s, peminjam_nama = %s, peminjam_nim = %s, tanggal_peminjaman = %s, tanggal_batas_pengembalian = %s
                    WHERE judul = %s
                """, ('dipinjam', nama, nim, tanggal_pinjam_obj, tanggal_batas_pengembalian, judul))

                mysql.connection.commit()
                flash(f"Buku '{judul}' berhasil dipinjam oleh {nama}.", "success")
            else:
                flash(f"Maaf, Buku '{judul}' tidak tersedia atau sudah dipinjam.", "error")
        except ValueError:
            flash("Tanggal yang Anda masukkan tidak valid.", "error")
        finally:
            if cur:
                cur.close()
                
    @staticmethod
    def kembalikan_buku(judul, tanggal_kembali):
        # Fungsi untuk mengembalikan buku
        cur = None
        try:
            if not tanggal_kembali:
                flash("Tanggal kembali tidak valid.", "error")
                return None

            tanggal_kembali_obj = datetime.strptime(tanggal_kembali, "%Y-%m-%d")

            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM buku WHERE judul = %s AND status = 'dipinjam'", (judul,))
            buku = cur.fetchone()

            if buku:
                tanggal_batas_pengembalian = buku['tanggal_batas_pengembalian']
                if isinstance(tanggal_batas_pengembalian, datetime):
                    tanggal_batas_pengembalian_date = tanggal_batas_pengembalian.date()
                else:
                    tanggal_batas_pengembalian_date = tanggal_batas_pengembalian

                terlambat = (tanggal_kembali_obj.date() - tanggal_batas_pengembalian_date).days
                denda = terlambat * 2000 if terlambat > 0 else 0

                cur.execute("""
                    UPDATE buku
                    SET status = %s, peminjam_nama = NULL, peminjam_nim = NULL, tanggal_peminjaman = NULL, tanggal_batas_pengembalian = NULL
                    WHERE judul = %s
                """, ('tersedia', judul))

                mysql.connection.commit()
                return terlambat, denda, buku['peminjam_nama'], buku['peminjam_nim'], buku['tanggal_peminjaman'], buku['tanggal_batas_pengembalian'], buku['genre']
                
        except ValueError:
            flash("Tanggal yang Anda masukkan tidak valid.", "error")
        finally:
            if cur:
                cur.close()
        return None

    @staticmethod
    def insert_into_history(db, buku, tanggal_kembali, terlambat, denda, peminjam_data, tanggal_peminjaman, tanggal_batas_pengembalian):
        # Fungsi untuk memasukkan data ke dalam tabel history
        cursor = db.connection.cursor()
        sql = """
        INSERT INTO history (judul, genre, peminjam_nama, peminjam_nim, tanggal_peminjaman, tanggal_batas_pengembalian, tanggal_pengembalian, jumlah_hari_terlambat, biaya_denda)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        val = (
            buku['judul'], 
            buku['genre'], 
            peminjam_data['nama'], 
            peminjam_data['nim'], 
            tanggal_peminjaman, 
            tanggal_batas_pengembalian, 
            tanggal_kembali, 
            terlambat if terlambat > 0 else 0,  # Pastikan nol jika tidak terlambat
            denda if denda > 0 else 0  # Pastikan nol jika tidak ada denda
        )
        cursor.execute(sql, val)
        db.connection.commit()
        cursor.close()

@app.route('/pinjamBuku', methods=['GET', 'POST'])
def pinjam():
    # Halaman untuk meminjam buku
    if request.method == 'POST':
        judul_buku = request.form.get("judul")
        name = request.form.get("name")
        nim = request.form.get("nim")
        tanggal_pinjam = request.form.get("tanggal-pinjam")

        Perpustakaan.pinjam_buku(judul_buku, name, nim, tanggal_pinjam)
        return redirect(url_for('pinjam'))
    return render_template('pinjamBuku.html')

@app.route('/kembali', methods=['GET', 'POST'])
def kembali():
    # Halaman untuk mengembalikan buku
    if request.method == 'POST':
        judul_buku = request.form.get("judul")
        tanggal_kembali = request.form.get("tanggal-kembali")

        result = Perpustakaan.kembalikan_buku(judul_buku, tanggal_kembali)

        if result:
            terlambat, denda, peminjam_nama, peminjam_nim, tanggal_peminjaman, tanggal_batas_pengembalian, genre = result
            buku = {'judul': judul_buku, 'genre': genre}
            peminjam_data = {'nama': peminjam_nama, 'nim': peminjam_nim}
            Perpustakaan.insert_into_history(mysql, buku, tanggal_kembali, terlambat, denda, peminjam_data, tanggal_peminjaman, tanggal_batas_pengembalian)

            if terlambat > 0:
                flash(f"Anda terlambat mengembalikan buku selama {terlambat} hari. Denda: Rp {denda}", "error")
            else:
                flash("Buku dikembalikan tepat waktu.", "success")
        else:
            flash("Gagal mengembalikan buku", "error")

        return redirect(url_for('kembali'))
    return render_template('kembaliBuku.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    # Halaman pencarian buku
    if request.method == 'POST':
        search_query = request.form['search_query']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT judul, genre, status FROM buku WHERE judul LIKE %s", (f"%{search_query}%",))
        books = cursor.fetchall()
        cursor.close()
        return render_template('search.html', books=books, query=search_query)
    return render_template('search.html')

@app.route('/logout')
def logout():
    # Menghapus sesi dan mengarahkan ke halaman login
    session.clear()
    return redirect(url_for('home'))

# Menjalankan aplikasi Flask
if __name__ == '__main__':
    app.run(debug=True, port=5001)