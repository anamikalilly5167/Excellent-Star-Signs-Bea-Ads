import os
import re
import secrets
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "store.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif", "svg"}
ALL_PERMISSIONS = ["services", "categories", "images", "contacts", "enquiries"]

app = Flask(__name__)
app.secret_key = "dev-secret-change-in-production"
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'sub',
        permissions TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS company (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        logo_path TEXT,
        sort_order INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS category (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER REFERENCES company(id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        sort_order INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS service (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL REFERENCES category(id) ON DELETE CASCADE,
        company_id INTEGER REFERENCES company(id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        description TEXT,
        price TEXT,
        image_path TEXT,
        badge TEXT,
        sort_order INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS gallery_image (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER REFERENCES category(id) ON DELETE SET NULL,
        title TEXT,
        image_path TEXT NOT NULL,
        featured_hero INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS banner (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        subtitle TEXT,
        image_path TEXT,
        sort_order INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS site_setting (
        key TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS enquiry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        message TEXT,
        service_name TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'new'
    );

    CREATE TABLE IF NOT EXISTS review (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        comment TEXT,
        photo_path TEXT,
        token TEXT UNIQUE,
        approved INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()

    existing_cols = [r["name"] for r in conn.execute("PRAGMA table_info(gallery_image)").fetchall()]
    if "featured_hero" not in existing_cols:
        conn.execute("ALTER TABLE gallery_image ADD COLUMN featured_hero INTEGER DEFAULT 0")
        conn.commit()

    admin_cols = [r["name"] for r in conn.execute("PRAGMA table_info(admin)").fetchall()]
    if "username" in admin_cols and "email" not in admin_cols:
        conn.execute("ALTER TABLE admin RENAME COLUMN username TO email")
        conn.commit()

    if not conn.execute("SELECT 1 FROM admin").fetchone():
        conn.execute(
            "INSERT INTO admin (email, password_hash, role, permissions) VALUES (?, ?, 'super', ?)",
            ("excellentstarsigns@gmail.com", generate_password_hash("excellent686"), ",".join(ALL_PERMISSIONS)),
        )

    default_settings = {
        "phone_1": "+91 98765 43210",
        "phone_2": "+91 91234 56789",
        "landline": "0484-2345678",
        "email": "info@excellentstarsigns.com",
        "address": "123 Industrial Estate, Kochi, Kerala, India",
        "facebook": "#",
        "instagram": "#",
        "whatsapp": "#",
        "site_title": "Excellent Star Signs & Bea Ads",
        "tagline": "Signage, Printing & Branding Solutions",
        "map_embed_url": "",
        "business_hours": "Mon - Sat: 9:30 AM - 7:00 PM\nSunday: Closed",
        "logo_path": "uploads/logo.png",
    }
    for k, v in default_settings.items():
        conn.execute(
            "INSERT OR IGNORE INTO site_setting (key, value) VALUES (?, ?)", (k, v)
        )

    if not conn.execute("SELECT 1 FROM company").fetchone():
        conn.execute(
            "INSERT INTO company (name, slug, sort_order) VALUES (?, ?, ?)",
            ("Excellent Star Signs", "excellent-star-signs", 1),
        )
        conn.execute(
            "INSERT INTO company (name, slug, sort_order) VALUES (?, ?, ?)",
            ("Bea Ads", "bea-ads", 2),
        )
    conn.commit()

    if not conn.execute("SELECT 1 FROM category").fetchone():
        ess_id = conn.execute(
            "SELECT id FROM company WHERE slug='excellent-star-signs'"
        ).fetchone()["id"]
        bea_id = conn.execute(
            "SELECT id FROM company WHERE slug='bea-ads'"
        ).fetchone()["id"]

        ess_categories = [
            "Sign Boards", "LED Boards", "ACP Boards", "Acrylic Letters",
            "Metal 3D Letters", "Name Plates", "Hoardings", "Cloth Banners",
            "Flex Banners", "Vinyl Works", "In-Shop Branding",
        ]
        bea_categories = [
            "Printing", "Designing", "Brochures", "Flyers",
            "Visiting Cards", "Posters", "Marketing Materials",
        ]

        i = 0
        for name in ess_categories:
            conn.execute(
                "INSERT INTO category (company_id, name, slug, sort_order) VALUES (?, ?, ?, ?)",
                (ess_id, name, slugify(name), i),
            )
            i += 1
        for name in bea_categories:
            conn.execute(
                "INSERT INTO category (company_id, name, slug, sort_order) VALUES (?, ?, ?, ?)",
                (bea_id, name, slugify(name), i),
            )
            i += 1
        conn.commit()

    conn.close()


def slugify(text):
    return "-".join(text.lower().strip().split())


def is_valid_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def current_admin():
    if not session.get("admin_id"):
        return None
    conn = get_db()
    row = conn.execute("SELECT * FROM admin WHERE id=?", (session["admin_id"],)).fetchone()
    conn.close()
    return row


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


def super_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        admin = current_admin()
        if not admin:
            return redirect(url_for("admin_login"))
        if admin["role"] != "super":
            flash("Only the Super Admin can access this page.")
            return redirect(url_for("admin_dashboard"))
        return f(*args, **kwargs)
    return wrapper


def permission_required(perm):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            admin = current_admin()
            if not admin:
                return redirect(url_for("admin_login"))
            if admin["role"] != "super" and perm not in (admin["permissions"] or "").split(","):
                flash("You don't have permission to access this section.")
                return redirect(url_for("admin_dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def get_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM site_setting").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def save_upload(file_storage, prefix=""):
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        return None
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    fname = secure_filename(f"{prefix}{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.{ext}")
    file_storage.save(os.path.join(UPLOAD_DIR, fname))
    return f"uploads/{fname}"


# ---------- Public routes ----------

@app.route("/")
def index():
    conn = get_db()
    categories = conn.execute("SELECT * FROM category ORDER BY sort_order").fetchall()
    hero_images = conn.execute(
        "SELECT * FROM gallery_image WHERE featured_hero=1 ORDER BY sort_order, created_at DESC LIMIT 5"
    ).fetchall()
    banner = conn.execute(
        "SELECT * FROM banner ORDER BY sort_order LIMIT 1"
    ).fetchone()
    best_sellers = conn.execute(
        """SELECT s.*, c.name AS category_name FROM service s
           JOIN category c ON s.category_id = c.id
           ORDER BY s.created_at DESC LIMIT 8"""
    ).fetchall()
    reviews = conn.execute(
        "SELECT * FROM review WHERE approved=1 ORDER BY created_at DESC LIMIT 12"
    ).fetchall()
    review_stats = conn.execute(
        "SELECT COUNT(*) c, AVG(rating) avg FROM review WHERE approved=1"
    ).fetchone()
    conn.close()
    settings = get_settings()
    return render_template(
        "index.html",
        categories=categories,
        hero_images=hero_images,
        banner=banner,
        services=best_sellers,
        settings=settings,
        active_category=None,
        reviews=reviews,
        review_stats=review_stats,
    )


@app.route("/category/<slug>")
def category_view(slug):
    conn = get_db()
    category = conn.execute(
        "SELECT * FROM category WHERE slug=?", (slug,)
    ).fetchone()
    if not category:
        conn.close()
        return redirect(url_for("index"))
    categories = conn.execute("SELECT * FROM category ORDER BY sort_order").fetchall()
    services = conn.execute(
        "SELECT * FROM service WHERE category_id=? ORDER BY sort_order, created_at DESC",
        (category["id"],),
    ).fetchall()
    conn.close()
    settings = get_settings()
    return render_template(
        "category.html",
        categories=categories,
        category=category,
        services=services,
        settings=settings,
        active_category=category["id"],
    )


@app.route("/service/<int:service_id>")
def service_detail(service_id):
    conn = get_db()
    service = conn.execute(
        "SELECT s.*, c.name AS category_name, c.slug AS category_slug, "
        "comp.name AS company_name FROM service s "
        "JOIN category c ON s.category_id = c.id "
        "LEFT JOIN company comp ON s.company_id = comp.id WHERE s.id=?", (service_id,)
    ).fetchone()
    if not service:
        conn.close()
        return redirect(url_for("index"))
    categories = conn.execute("SELECT * FROM category ORDER BY sort_order").fetchall()
    conn.close()
    settings = get_settings()
    return render_template(
        "service_detail.html",
        categories=categories,
        service=service,
        settings=settings,
        active_category=service["category_id"],
    )


@app.route("/gallery")
def gallery():
    conn = get_db()
    categories = conn.execute("SELECT * FROM category ORDER BY sort_order").fetchall()
    images = conn.execute(
        "SELECT g.*, c.name AS category_name FROM gallery_image g "
        "LEFT JOIN category c ON g.category_id = c.id ORDER BY g.sort_order, g.created_at DESC"
    ).fetchall()
    conn.close()
    settings = get_settings()
    return render_template(
        "gallery.html",
        categories=categories,
        images=images,
        settings=settings,
        active_category=None,
    )


@app.route("/contact")
def contact():
    conn = get_db()
    categories = conn.execute("SELECT * FROM category ORDER BY sort_order").fetchall()
    conn.close()
    settings = get_settings()
    return render_template(
        "contact.html",
        categories=categories,
        settings=settings,
        active_category=None,
    )


@app.route("/enquiry", methods=["POST"])
def submit_enquiry():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()
    service_name = request.form.get("service_name", "").strip()

    if not name or not phone:
        return jsonify({"ok": False, "error": "Name and phone are required."}), 400

    conn = get_db()
    conn.execute(
        "INSERT INTO enquiry (name, phone, email, message, service_name) VALUES (?, ?, ?, ?, ?)",
        (name, phone, email, message, service_name),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ---------- Admin auth ----------

@app.after_request
def no_cache_admin(response):
    if request.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        admin = conn.execute(
            "SELECT * FROM admin WHERE email=?", (email,)
        ).fetchone()
        conn.close()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            return jsonify({"ok": True, "redirect": url_for("admin_dashboard")})
        return jsonify({"ok": False, "error": "Invalid email or password."}), 401
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin/session-check")
def admin_session_check():
    return jsonify({"logged_in": bool(session.get("admin_id"))})


# ---------- Admin dashboard ----------

@app.route("/admin")
@login_required
def admin_dashboard():
    conn = get_db()
    counts = {
        "categories": conn.execute("SELECT COUNT(*) c FROM category").fetchone()["c"],
        "services": conn.execute("SELECT COUNT(*) c FROM service").fetchone()["c"],
        "gallery": conn.execute("SELECT COUNT(*) c FROM gallery_image").fetchone()["c"],
        "enquiries": conn.execute("SELECT COUNT(*) c FROM enquiry WHERE status='new'").fetchone()["c"],
        "reviews_pending": conn.execute("SELECT COUNT(*) c FROM review WHERE approved=0").fetchone()["c"],
    }
    recent_enquiries = conn.execute(
        "SELECT * FROM enquiry ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return render_template(
        "admin/dashboard.html", counts=counts, recent_enquiries=recent_enquiries, me=current_admin()
    )


# ---------- Admin: Categories ----------

@app.route("/admin/categories", methods=["GET", "POST"])
@login_required
@permission_required("categories")
def admin_categories():
    conn = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        company_id = request.form.get("company_id") or None
        if name:
            base_slug = slugify(name)
            slug = base_slug
            n = 1
            while conn.execute("SELECT 1 FROM category WHERE slug=?", (slug,)).fetchone():
                n += 1
                slug = f"{base_slug}-{n}"
            conn.execute(
                "INSERT INTO category (company_id, name, slug, sort_order) VALUES (?, ?, ?, ?)",
                (company_id, name, slug, 99),
            )
            conn.commit()
        conn.close()
        return redirect(url_for("admin_categories"))
    categories = conn.execute(
        "SELECT cat.*, comp.name AS company_name FROM category cat "
        "LEFT JOIN company comp ON cat.company_id = comp.id ORDER BY cat.sort_order"
    ).fetchall()
    companies = conn.execute("SELECT * FROM company ORDER BY sort_order").fetchall()
    conn.close()
    return render_template("admin/categories.html", categories=categories, companies=companies, me=current_admin())


@app.route("/admin/categories/<int:category_id>/edit", methods=["POST"])
@login_required
@permission_required("categories")
def admin_category_edit(category_id):
    name = request.form.get("name", "").strip()
    company_id = request.form.get("company_id") or None
    conn = get_db()
    conn.execute(
        "UPDATE category SET name=?, company_id=? WHERE id=?",
        (name, company_id, category_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
@login_required
@permission_required("categories")
def admin_category_delete(category_id):
    conn = get_db()
    conn.execute("DELETE FROM category WHERE id=?", (category_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_categories"))


# ---------- Admin: Services ----------

@app.route("/admin/services", methods=["GET", "POST"])
@login_required
@permission_required("services")
def admin_services():
    conn = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category_id = request.form.get("category_id")
        company_id = request.form.get("company_id") or None
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        badge = request.form.get("badge", "").strip()
        if name and category_id:
            image_path = save_upload(request.files.get("image"), prefix="svc_")
            conn.execute(
                "INSERT INTO service (category_id, company_id, name, description, price, image_path, badge, sort_order) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (category_id, company_id, name, description, price, image_path, badge, 99),
            )
            conn.commit()
        conn.close()
        return redirect(url_for("admin_services"))
    services = conn.execute(
        "SELECT s.*, c.name AS category_name, comp.name AS company_name FROM service s "
        "JOIN category c ON s.category_id = c.id "
        "LEFT JOIN company comp ON s.company_id = comp.id ORDER BY s.created_at DESC"
    ).fetchall()
    categories = conn.execute("SELECT * FROM category ORDER BY sort_order").fetchall()
    companies = conn.execute("SELECT * FROM company ORDER BY sort_order").fetchall()
    conn.close()
    return render_template(
        "admin/services.html", services=services, categories=categories, companies=companies, me=current_admin()
    )


@app.route("/admin/services/<int:service_id>/edit", methods=["POST"])
@login_required
@permission_required("services")
def admin_service_edit(service_id):
    name = request.form.get("name", "").strip()
    category_id = request.form.get("category_id")
    company_id = request.form.get("company_id") or None
    description = request.form.get("description", "").strip()
    price = request.form.get("price", "").strip()
    badge = request.form.get("badge", "").strip()
    conn = get_db()
    image_file = request.files.get("image")
    if image_file and image_file.filename:
        image_path = save_upload(image_file, prefix="svc_")
        conn.execute(
            "UPDATE service SET name=?, category_id=?, company_id=?, description=?, price=?, badge=?, image_path=? WHERE id=?",
            (name, category_id, company_id, description, price, badge, image_path, service_id),
        )
    else:
        conn.execute(
            "UPDATE service SET name=?, category_id=?, company_id=?, description=?, price=?, badge=? WHERE id=?",
            (name, category_id, company_id, description, price, badge, service_id),
        )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_services"))


@app.route("/admin/services/<int:service_id>/delete", methods=["POST"])
@login_required
@permission_required("services")
def admin_service_delete(service_id):
    conn = get_db()
    conn.execute("DELETE FROM service WHERE id=?", (service_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_services"))


# ---------- Admin: Gallery ----------

@app.route("/admin/gallery", methods=["GET", "POST"])
@login_required
@permission_required("images")
def admin_gallery():
    conn = get_db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category_id = request.form.get("category_id") or None
        image_path = save_upload(request.files.get("image"), prefix="gal_")
        if image_path:
            conn.execute(
                "INSERT INTO gallery_image (category_id, title, image_path, sort_order) VALUES (?, ?, ?, 99)",
                (category_id, title, image_path),
            )
            conn.commit()
        conn.close()
        return redirect(url_for("admin_gallery"))
    images = conn.execute(
        "SELECT g.*, c.name AS category_name FROM gallery_image g "
        "LEFT JOIN category c ON g.category_id = c.id ORDER BY g.created_at DESC"
    ).fetchall()
    categories = conn.execute("SELECT * FROM category ORDER BY sort_order").fetchall()
    conn.close()
    return render_template("admin/gallery.html", images=images, categories=categories, me=current_admin())


@app.route("/admin/gallery/<int:image_id>/edit", methods=["POST"])
@login_required
@permission_required("images")
def admin_gallery_edit(image_id):
    title = request.form.get("title", "").strip()
    category_id = request.form.get("category_id") or None
    conn = get_db()
    conn.execute(
        "UPDATE gallery_image SET title=?, category_id=? WHERE id=?",
        (title, category_id, image_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_gallery"))


@app.route("/admin/gallery/<int:image_id>/feature", methods=["POST"])
@login_required
@permission_required("images")
def admin_gallery_feature(image_id):
    conn = get_db()
    img = conn.execute("SELECT featured_hero FROM gallery_image WHERE id=?", (image_id,)).fetchone()
    if img and not img["featured_hero"]:
        count = conn.execute(
            "SELECT COUNT(*) c FROM gallery_image WHERE featured_hero=1"
        ).fetchone()["c"]
        if count >= 5:
            flash("You can feature at most 5 images in the hero. Unfeature one first.")
            conn.close()
            return redirect(url_for("admin_gallery"))
    conn.execute("UPDATE gallery_image SET featured_hero = 1 - featured_hero WHERE id=?", (image_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_gallery"))


@app.route("/admin/gallery/<int:image_id>/delete", methods=["POST"])
@login_required
@permission_required("images")
def admin_gallery_delete(image_id):
    conn = get_db()
    conn.execute("DELETE FROM gallery_image WHERE id=?", (image_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_gallery"))


# ---------- Admin: Banner & Logo ----------

@app.route("/admin/banners", methods=["GET", "POST"])
@login_required
@permission_required("images")
def admin_banners():
    conn = get_db()
    if request.method == "POST":
        if "banner_image" in request.files and request.files["banner_image"].filename:
            image_path = save_upload(request.files.get("banner_image"), prefix="banner_")
            if image_path:
                conn.execute("DELETE FROM banner")
                conn.execute(
                    "INSERT INTO banner (image_path, sort_order, active) VALUES (?, 0, 1)",
                    (image_path,),
                )
        if "logo_image" in request.files and request.files["logo_image"].filename:
            logo_path = save_upload(request.files.get("logo_image"), prefix="sitelogo_")
            if logo_path:
                conn.execute(
                    "INSERT INTO site_setting (key, value) VALUES ('logo_path', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (logo_path,),
                )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_banners"))
    banner = conn.execute("SELECT * FROM banner ORDER BY sort_order LIMIT 1").fetchone()
    conn.close()
    return render_template("admin/banners.html", banner=banner, me=current_admin())


@app.route("/admin/banners/remove", methods=["POST"])
@login_required
@permission_required("images")
def admin_banner_remove():
    conn = get_db()
    conn.execute("DELETE FROM banner")
    conn.commit()
    conn.close()
    return redirect(url_for("admin_banners"))


# ---------- Admin: Settings ----------

@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
@permission_required("contacts")
def admin_settings():
    conn = get_db()
    if request.method == "POST":
        for key in request.form:
            conn.execute(
                "INSERT INTO site_setting (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, request.form[key]),
            )
        conn.commit()
        flash("Settings updated.")
    settings = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM site_setting").fetchall()}
    conn.close()
    return render_template("admin/settings.html", settings=settings, me=current_admin())


# ---------- Admin: Enquiries ----------

@app.route("/admin/enquiries")
@login_required
@permission_required("enquiries")
def admin_enquiries():
    conn = get_db()
    enquiries = conn.execute("SELECT * FROM enquiry ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin/enquiries.html", enquiries=enquiries, me=current_admin())


@app.route("/admin/enquiries/<int:enquiry_id>/contacted", methods=["POST"])
@login_required
@permission_required("enquiries")
def admin_enquiry_contacted(enquiry_id):
    conn = get_db()
    conn.execute("UPDATE enquiry SET status='contacted' WHERE id=?", (enquiry_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_enquiries"))


@app.route("/admin/enquiries/<int:enquiry_id>/delete", methods=["POST"])
@login_required
@permission_required("enquiries")
def admin_enquiry_delete(enquiry_id):
    conn = get_db()
    conn.execute("DELETE FROM enquiry WHERE id=?", (enquiry_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_enquiries"))


# ---------- Admin: Sub Admins (Super Admin only) ----------

@app.route("/admin/sub-admins", methods=["GET", "POST"])
@login_required
@super_required
def admin_sub_admins():
    conn = get_db()
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        perms = request.form.getlist("permissions")
        if not is_valid_email(email):
            flash("Enter a valid email address.")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.")
        else:
            try:
                conn.execute(
                    "INSERT INTO admin (email, password_hash, role, permissions) VALUES (?, ?, 'sub', ?)",
                    (email, generate_password_hash(password), ",".join(perms)),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                flash("That email is already registered.")
        conn.close()
        return redirect(url_for("admin_sub_admins"))
    sub_admins = conn.execute("SELECT * FROM admin WHERE role='sub' ORDER BY created_at").fetchall()
    conn.close()
    return render_template(
        "admin/sub_admins.html", sub_admins=sub_admins, all_permissions=ALL_PERMISSIONS, me=current_admin()
    )


@app.route("/admin/sub-admins/<int:admin_id>/edit", methods=["POST"])
@login_required
@super_required
def admin_sub_admin_edit(admin_id):
    password = request.form.get("password", "").strip()
    perms = request.form.getlist("permissions")
    if password and len(password) < 6:
        flash("Password must be at least 6 characters.")
        return redirect(url_for("admin_sub_admins"))
    conn = get_db()
    if password:
        conn.execute(
            "UPDATE admin SET password_hash=?, permissions=? WHERE id=? AND role='sub'",
            (generate_password_hash(password), ",".join(perms), admin_id),
        )
    else:
        conn.execute(
            "UPDATE admin SET permissions=? WHERE id=? AND role='sub'",
            (",".join(perms), admin_id),
        )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_sub_admins"))


@app.route("/admin/sub-admins/<int:admin_id>/delete", methods=["POST"])
@login_required
@super_required
def admin_sub_admin_delete(admin_id):
    conn = get_db()
    conn.execute("DELETE FROM admin WHERE id=? AND role='sub'", (admin_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_sub_admins"))


@app.route("/admin/account", methods=["GET", "POST"])
@login_required
@super_required
def admin_account():
    conn = get_db()
    me = current_admin()
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        if not is_valid_email(email):
            flash("Enter a valid email address.")
        elif password and len(password) < 6:
            flash("Password must be at least 6 characters.")
        else:
            try:
                if password:
                    conn.execute(
                        "UPDATE admin SET email=?, password_hash=? WHERE id=?",
                        (email, generate_password_hash(password), me["id"]),
                    )
                    conn.commit()
                    conn.close()
                    session.clear()
                    flash("Credentials updated. Please log in again.")
                    return redirect(url_for("admin_login"))
                else:
                    conn.execute("UPDATE admin SET email=? WHERE id=?", (email, me["id"]))
                    conn.commit()
                    flash("Email updated.")
            except sqlite3.IntegrityError:
                flash("That email is already registered.")
    conn.close()
    return render_template("admin/account.html", me=current_admin())


# ---------- Reviews: Public ----------

@app.route("/review/<token>")
def review_form(token):
    conn = get_db()
    review = conn.execute("SELECT * FROM review WHERE token=?", (token,)).fetchone()
    conn.close()
    if not review:
        return "Invalid or expired review link.", 404
    if review["approved"] == 2:  # already submitted
        return render_template("review_done.html")
    settings = get_settings()
    return render_template("review_form.html", token=token, review=review, settings=settings)


@app.route("/review/<token>/submit", methods=["POST"])
def review_submit(token):
    conn = get_db()
    review = conn.execute("SELECT * FROM review WHERE token=?", (token,)).fetchone()
    if not review or review["approved"] == 2:
        conn.close()
        return jsonify({"ok": False, "error": "Invalid or already submitted."}), 400
    rating = request.form.get("rating", "").strip()
    comment = request.form.get("comment", "").strip()
    name = request.form.get("name", review["name"]).strip()
    if not rating or not rating.isdigit() or not (1 <= int(rating) <= 5):
        conn.close()
        return jsonify({"ok": False, "error": "Please select a star rating."}), 400
    photo_path = None
    if "photo" in request.files and request.files["photo"].filename:
        photo_path = save_upload(request.files["photo"], prefix="rev_")
    conn.execute(
        "UPDATE review SET rating=?, comment=?, name=?, photo_path=COALESCE(?, photo_path), approved=0 WHERE token=?",
        (int(rating), comment, name, photo_path, token),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/review-invite", methods=["POST"])
def review_invite():
    """Admin sends a review invite: creates a token row and returns the link."""
    if not session.get("admin_id"):
        return jsonify({"ok": False}), 403
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Name is required."}), 400
    token = secrets.token_urlsafe(24)
    conn = get_db()
    conn.execute(
        "INSERT INTO review (name, email, rating, token, approved) VALUES (?, ?, 1, ?, 3)",
        (name, email, token),
    )
    conn.commit()
    conn.close()
    link = url_for("review_form", token=token, _external=True)
    return jsonify({"ok": True, "link": link})


# ---------- Admin: Reviews ----------

@app.route("/admin/reviews")
@login_required
def admin_reviews():
    conn = get_db()
    reviews = conn.execute("SELECT * FROM review WHERE approved NOT IN (2, 3) ORDER BY created_at DESC").fetchall()
    pending_invites = conn.execute("SELECT * FROM review WHERE approved = 3 ORDER BY created_at DESC").fetchall()
    stats = conn.execute(
        "SELECT COUNT(*) c, AVG(rating) avg FROM review WHERE approved=1"
    ).fetchone()
    conn.close()
    return render_template(
        "admin/reviews.html",
        reviews=reviews,
        pending_invites=pending_invites,
        stats=stats,
        me=current_admin(),
    )


@app.route("/admin/reviews/<int:review_id>/approve", methods=["POST"])
@login_required
def admin_review_approve(review_id):
    conn = get_db()
    conn.execute("UPDATE review SET approved=1 WHERE id=?", (review_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_reviews"))


@app.route("/admin/reviews/<int:review_id>/reject", methods=["POST"])
@login_required
def admin_review_reject(review_id):
    conn = get_db()
    conn.execute("UPDATE review SET approved=-1 WHERE id=?", (review_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_reviews"))


@app.route("/admin/reviews/<int:review_id>/delete", methods=["POST"])
@login_required
def admin_review_delete(review_id):
    conn = get_db()
    conn.execute("DELETE FROM review WHERE id=?", (review_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_reviews"))


@app.context_processor
def inject_logo():
    return {"logo_path": get_settings().get("logo_path", "uploads/logo.png")}


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)