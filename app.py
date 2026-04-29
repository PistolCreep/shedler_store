from __future__ import annotations

import os
import sqlite3
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "instance" / "shedler.db"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"

app = Flask(__name__)
app.config["SECRET_KEY"] = "shedler-diploma-secret-key-change-me"
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATABASE.parent.mkdir(parents=True, exist_ok=True)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_: Optional[BaseException]) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_db(query: str, params: tuple = (), one: bool = False) -> Any:
    cur = get_db().execute(query, params)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute_db(query: str, params: tuple = ()) -> int:
    db = get_db()
    cur = db.execute(query, params)
    db.commit()
    last_row_id = cur.lastrowid
    cur.close()
    return last_row_id


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            price INTEGER NOT NULL,
            area REAL NOT NULL,
            rooms INTEGER NOT NULL,
            capacity INTEGER NOT NULL,
            seasonality TEXT NOT NULL,
            production_time TEXT NOT NULL,
            short_description TEXT NOT NULL,
            description TEXT NOT NULL,
            specs TEXT NOT NULL,
            image_url TEXT,
            is_featured INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            client_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'Новая',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS contacts_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS site_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_key TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            body TEXT NOT NULL
        );
        """
    )
    db.commit()

    admin_exists = query_db("SELECT id FROM admins LIMIT 1", one=True)
    if not admin_exists:
        execute_db(
            "INSERT INTO admins (username, password_hash, full_name) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "Администратор ООО «Шедлер»"),
        )

    if not query_db("SELECT id FROM categories LIMIT 1", one=True):
        seed_categories()
    if not query_db("SELECT id FROM products LIMIT 1", one=True):
        seed_products()
    if not query_db("SELECT id FROM site_content LIMIT 1", one=True):
        seed_content()


def seed_categories() -> None:
    categories = [
        ("Дома для баз отдыха", "base-otdyha", "Компактные и комфортные решения для туристических объектов."),
        ("Глэмпинг-модули", "glamping", "Модели для премиального отдыха и привлекательного размещения гостей."),
        ("Гостевые дома", "guest-house", "Домики для краткосрочного и длительного размещения."),
        ("Служебные модули", "service", "Административные, санитарные и вспомогательные модули."),
    ]
    for item in categories:
        execute_db("INSERT INTO categories (name, slug, description) VALUES (?, ?, ?)", item)


def seed_products() -> None:
    category_map = {row["slug"]: row["id"] for row in query_db("SELECT id, slug FROM categories")}
    products = [
        (
            category_map["base-otdyha"],
            "Shedler Forest 24",
            "shedler-forest-24",
            1450000,
            24,
            1,
            2,
            "Круглогодичное",
            "от 25 дней",
            "Компактный модульный дом для баз отдыха и туристических комплексов.",
            "Модель Shedler Forest 24 разработана для размещения 2 гостей и подходит для установки на территории базы отдыха, глэмпинга или загородного комплекса. Дом оснащается утепленным каркасом, панорамным остеклением и возможностью индивидуальной отделки.",
            "Каркас: металлический усиленный\nУтепление: минеральная вата 150 мм\nОтделка: имитация бруса / ЛДСП\nСанузел: опционально\nЭлектрика: базовая разводка\nТеплый пол: опция",
            "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=80",
            1,
        ),
        (
            category_map["glamping"],
            "Shedler Lake 36",
            "shedler-lake-36",
            2190000,
            36,
            2,
            4,
            "Круглогодичное",
            "от 35 дней",
            "Современный глэмпинг-модуль с террасой и продуманной планировкой.",
            "Shedler Lake 36 — универсальный модульный дом для размещения семей или пар. Подходит для турбаз и глэмпинг-парков, где важны эстетика, скорость монтажа и высокий уровень комфорта.",
            "Каркас: металлокаркас\nУтепление: PIR-панели\nОкна: панорамные стеклопакеты\nТерраса: входит в базовую комплектацию\nСанузел: встроенный\nКухонная зона: предусмотрена",
            "https://images.unsplash.com/photo-1448630360428-65456885c650?auto=format&fit=crop&w=1200&q=80",
            1,
        ),
        (
            category_map["guest-house"],
            "Shedler Family 48",
            "shedler-family-48",
            2980000,
            48,
            3,
            6,
            "Круглогодичное",
            "от 45 дней",
            "Просторный гостевой дом для размещения семей и больших компаний.",
            "Модель ориентирована на владельцев баз отдыха, которым важно увеличить вместимость объекта и предложить гостям полноценный уровень проживания. Подходит как под краткосрочную аренду, так и под длительное проживание персонала.",
            "Каркас: металлический\nУтепление: 200 мм\nОтделка фасада: фиброцементные панели\nКомнаты: 3\nСанузел: 1\nКухня-гостиная: есть",
            "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1200&q=80",
            0,
        ),
        (
            category_map["service"],
            "Shedler Service 18",
            "shedler-service-18",
            990000,
            18,
            1,
            2,
            "Всесезонное",
            "от 20 дней",
            "Служебный модуль для администрации, охраны или санитарного блока.",
            "Практичное решение для создания административного пространства, ресепшена или служебного помещения на территории базы отдыха. Может использоваться как точка приема гостей или бытовой блок.",
            "Каркас: стальной\nУтепление: 100 мм\nНазначение: сервисный модуль\nСанузел: по запросу\nЭлектрика: включена\nВодоснабжение: опционально",
            "https://images.unsplash.com/photo-1494526585095-c41746248156?auto=format&fit=crop&w=1200&q=80",
            0,
        ),
        (
            category_map["base-otdyha"],
            "Shedler Eco 30",
            "shedler-eco-30",
            1720000,
            30,
            2,
            4,
            "Летнее / демисезонное",
            "от 28 дней",
            "Экономичное решение для быстрого расширения номерного фонда базы отдыха.",
            "Shedler Eco 30 подходит для сезонной эксплуатации и позволяет быстро организовать проживание гостей с минимальными затратами на строительство и монтаж.",
            "Каркас: облегченный металлический\nУтепление: 100 мм\nКомнаты: 2\nПлощадь: 30 м²\nМонтаж: 1–2 дня\nОтделка: базовая",
            "https://images.unsplash.com/photo-1502005229762-cf1b2da7c5d6?auto=format&fit=crop&w=1200&q=80",
            1,
        ),
    ]
    for item in products:
        execute_db(
            """
            INSERT INTO products (
                category_id, name, slug, price, area, rooms, capacity, seasonality,
                production_time, short_description, description, specs, image_url, is_featured
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            item,
        )


def seed_content() -> None:
    pages = [
        (
            "about",
            "О компании ООО «Шедлер»",
            "ООО «Шедлер» специализируется на проектировании, производстве и продаже модульных домов для туристических баз, глэмпингов и загородных комплексов. Компания ориентируется на быстрый монтаж, качественные материалы и адаптацию проектов под задачи заказчика.",
        ),
        (
            "delivery",
            "Доставка и монтаж",
            "Компания организует доставку модульных домов, подготовку площадки, монтаж и подключение инженерных коммуникаций. Сроки зависят от комплектации и удаленности объекта. Возможна поставка по индивидуальному графику для сезонных объектов размещения.",
        ),
        (
            "business",
            "Решения для бизнеса",
            "Модульные дома позволяют базам отдыха быстро расширять номерной фонд, создавать VIP-домики, административные модули, санитарные блоки и объекты для сезонной или круглогодичной эксплуатации. Решения подходят для турбаз, эко-парков и глэмпингов.",
        ),
    ]
    for item in pages:
        execute_db("INSERT INTO site_content (page_key, title, body) VALUES (?, ?, ?)", item)


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return view(**kwargs)

    return wrapped_view


def get_site_text(page_key: str) -> sqlite3.Row:
    row = query_db("SELECT * FROM site_content WHERE page_key = ?", (page_key,), one=True)
    if row is None:
        abort(404)
    return row


def get_favorites() -> List[int]:
    return session.get("favorites", [])


def format_price(value: int) -> str:
    return f"{value:,}".replace(",", " ")


@app.context_processor
def inject_globals() -> Dict[str, Any]:
    categories = query_db("SELECT * FROM categories ORDER BY name")
    favorites = get_favorites()
    compare = session.get("compare", [])
    return {
        "nav_categories": categories,
        "favorite_ids": favorites,
        "favorite_count": len(favorites),
        "compare_ids": compare,
        "compare_count": len(compare),
        "format_price": format_price,
    }


@app.route("/")
def home():
    featured = query_db(
        "SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id = p.category_id WHERE is_featured = 1 ORDER BY p.id DESC LIMIT 3"
    )
    return render_template("index.html", featured=featured)


@app.route("/catalog")
def catalog():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    seasonality = request.args.get("seasonality", "").strip()
    sort = request.args.get("sort", "popular").strip()

    sql = """
        SELECT p.*, c.name AS category_name, c.slug AS category_slug
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE 1=1
    """
    params: List[Any] = []

    if search:
        sql += " AND (p.name LIKE ? OR p.short_description LIKE ? OR p.description LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    if category:
        sql += " AND c.slug = ?"
        params.append(category)
    if seasonality:
        sql += " AND p.seasonality = ?"
        params.append(seasonality)

    order_by = {
        "price_asc": "p.price ASC",
        "price_desc": "p.price DESC",
        "area_asc": "p.area ASC",
        "area_desc": "p.area DESC",
        "popular": "p.is_featured DESC, p.id DESC",
    }.get(sort, "p.is_featured DESC, p.id DESC")
    sql += f" ORDER BY {order_by}"

    products = query_db(sql, tuple(params))
    seasonality_options = [row["seasonality"] for row in query_db("SELECT DISTINCT seasonality FROM products")]
    return render_template(
        "catalog.html",
        products=products,
        seasonality_options=seasonality_options,
        selected={"search": search, "category": category, "seasonality": seasonality, "sort": sort},
    )


@app.route("/product/<slug>")
def product_detail(slug: str):
    product = query_db(
        "SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id = p.category_id WHERE p.slug = ?",
        (slug,),
        one=True,
    )
    if product is None:
        abort(404)

    compare_ids = session.get("compare", [])
    compare_products = []
    if compare_ids:
        placeholders = ",".join("?" for _ in compare_ids)
        compare_products = query_db(
            f"SELECT id, name, area, price, rooms, seasonality FROM products WHERE id IN ({placeholders})",
            tuple(compare_ids),
        )
    return render_template("product_detail.html", product=product, compare_products=compare_products)


@app.route("/favorites")
def favorites():
    favorite_ids = get_favorites()
    products = []
    if favorite_ids:
        placeholders = ",".join("?" for _ in favorite_ids)
        products = query_db(f"SELECT * FROM products WHERE id IN ({placeholders})", tuple(favorite_ids))
    return render_template("favorites.html", products=products)


@app.route("/favorite/<int:product_id>")
def toggle_favorite(product_id: int):
    product = query_db("SELECT id FROM products WHERE id = ?", (product_id,), one=True)
    if product is None:
        abort(404)
    favorites = get_favorites()
    if product_id in favorites:
        favorites.remove(product_id)
        flash("Товар удален из избранного.", "info")
    else:
        favorites.append(product_id)
        flash("Товар добавлен в избранное.", "success")
    session["favorites"] = favorites
    return redirect(request.referrer or url_for("catalog"))


@app.route("/compare")
def compare_page():
    compare_ids = session.get("compare", [])
    products = []
    if compare_ids:
        placeholders = ",".join("?" for _ in compare_ids)
        products = query_db(
            f"SELECT id, name, slug, image_url, price, area, rooms, capacity, seasonality, production_time FROM products WHERE id IN ({placeholders})",
            tuple(compare_ids),
        )
    return render_template("compare.html", products=products)


@app.route("/compare/toggle/<int:product_id>")
def toggle_compare(product_id: int):
    product = query_db("SELECT id FROM products WHERE id = ?", (product_id,), one=True)
    if product is None:
        abort(404)
    compare = session.get("compare", [])
    if product_id in compare:
        compare.remove(product_id)
        flash("Товар убран из сравнения.", "info")
    else:
        if len(compare) >= 3:
            flash("Можно сравнить не более 3 домов одновременно.", "warning")
            return redirect(request.referrer or url_for("catalog"))
        compare.append(product_id)
        flash("Товар добавлен в сравнение.", "success")
    session["compare"] = compare
    return redirect(request.referrer or url_for("catalog"))


@app.route("/request", methods=["POST"])
def create_request():
    product_id = request.form.get("product_id")
    client_name = request.form.get("client_name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

    if not client_name or not phone:
        flash("Укажите имя и телефон.", "danger")
        return redirect(request.referrer or url_for("catalog"))

    pid = int(product_id) if product_id and product_id.isdigit() else None
    execute_db(
        "INSERT INTO requests (product_id, client_name, phone, email, message) VALUES (?, ?, ?, ?, ?)",
        (pid, client_name, phone, email, message),
    )
    flash("Заявка успешно отправлена. Менеджер свяжется с вами.", "success")
    return redirect(request.referrer or url_for("home"))


@app.route("/contacts", methods=["GET", "POST"])
def contacts():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        if not name or not message:
            flash("Укажите имя и текст сообщения.", "danger")
            return redirect(url_for("contacts"))
        execute_db(
            "INSERT INTO contacts_messages (name, phone, email, message) VALUES (?, ?, ?, ?)",
            (name, phone, email, message),
        )
        flash("Сообщение отправлено.", "success")
        return redirect(url_for("contacts"))
    return render_template("contacts.html")


@app.route("/about")
def about():
    page = get_site_text("about")
    return render_template("text_page.html", page=page, page_name="О компании")


@app.route("/delivery")
def delivery():
    page = get_site_text("delivery")
    return render_template("text_page.html", page=page, page_name="Доставка и монтаж")


@app.route("/business")
def business():
    page = get_site_text("business")
    return render_template("text_page.html", page=page, page_name="Решения для бизнеса")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = query_db("SELECT * FROM admins WHERE username = ?", (username,), one=True)
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["full_name"]
            flash("Вход выполнен.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Неверный логин или пароль.", "danger")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_name", None)
    flash("Вы вышли из админ-панели.", "info")
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    stats = {
        "products": query_db("SELECT COUNT(*) AS cnt FROM products", one=True)["cnt"],
        "requests": query_db("SELECT COUNT(*) AS cnt FROM requests", one=True)["cnt"],
        "new_requests": query_db("SELECT COUNT(*) AS cnt FROM requests WHERE status = 'Новая'", one=True)["cnt"],
        "categories": query_db("SELECT COUNT(*) AS cnt FROM categories", one=True)["cnt"],
    }
    last_requests = query_db(
        "SELECT r.*, p.name AS product_name FROM requests r LEFT JOIN products p ON p.id = r.product_id ORDER BY r.created_at DESC LIMIT 5"
    )
    return render_template("admin/dashboard.html", stats=stats, last_requests=last_requests)


@app.route("/admin/products")
@admin_required
def admin_products():
    products = query_db(
        "SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id = p.category_id ORDER BY p.id DESC"
    )
    return render_template("admin/products.html", products=products)


@app.route("/admin/products/create", methods=["GET", "POST"])
@admin_required
def admin_product_create():
    categories = query_db("SELECT * FROM categories ORDER BY name")
    if request.method == "POST":
        form = read_product_form(request)
        execute_db(
            """
            INSERT INTO products (
                category_id, name, slug, price, area, rooms, capacity, seasonality,
                production_time, short_description, description, specs, image_url, is_featured
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            form,
        )
        flash("Товар добавлен.", "success")
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", categories=categories, product=None)


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id: int):
    product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if product is None:
        abort(404)
    categories = query_db("SELECT * FROM categories ORDER BY name")
    if request.method == "POST":
        form = read_product_form(request)
        execute_db(
            """
            UPDATE products
            SET category_id=?, name=?, slug=?, price=?, area=?, rooms=?, capacity=?, seasonality=?,
                production_time=?, short_description=?, description=?, specs=?, image_url=?, is_featured=?
            WHERE id=?
            """,
            form + (product_id,),
        )
        flash("Товар обновлен.", "success")
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", categories=categories, product=product)


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def admin_product_delete(product_id: int):
    execute_db("DELETE FROM products WHERE id = ?", (product_id,))
    flash("Товар удален.", "info")
    return redirect(url_for("admin_products"))


@app.route("/admin/categories", methods=["GET", "POST"])
@admin_required
def admin_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = request.form.get("slug", "").strip()
        description = request.form.get("description", "").strip()
        if name and slug:
            execute_db("INSERT INTO categories (name, slug, description) VALUES (?, ?, ?)", (name, slug, description))
            flash("Категория добавлена.", "success")
        else:
            flash("Укажите название и slug категории.", "danger")
        return redirect(url_for("admin_categories"))
    categories = query_db("SELECT * FROM categories ORDER BY id DESC")
    return render_template("admin/categories.html", categories=categories)


@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def admin_category_delete(category_id: int):
    product_count = query_db("SELECT COUNT(*) AS cnt FROM products WHERE category_id = ?", (category_id,), one=True)["cnt"]
    if product_count > 0:
        flash("Нельзя удалить категорию, в которой есть товары.", "warning")
    else:
        execute_db("DELETE FROM categories WHERE id = ?", (category_id,))
        flash("Категория удалена.", "info")
    return redirect(url_for("admin_categories"))


@app.route("/admin/requests")
@admin_required
def admin_requests():
    requests_data = query_db(
        "SELECT r.*, p.name AS product_name FROM requests r LEFT JOIN products p ON p.id = r.product_id ORDER BY r.created_at DESC"
    )
    return render_template("admin/requests.html", requests_data=requests_data)


@app.route("/admin/requests/<int:request_id>/status", methods=["POST"])
@admin_required
def admin_request_status(request_id: int):
    status = request.form.get("status", "Новая")
    execute_db("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))
    flash("Статус заявки обновлен.", "success")
    return redirect(url_for("admin_requests"))


@app.route("/admin/content", methods=["GET", "POST"])
@admin_required
def admin_content():
    if request.method == "POST":
        page_key = request.form.get("page_key", "").strip()
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        execute_db("UPDATE site_content SET title=?, body=? WHERE page_key=?", (title, body, page_key))
        flash("Контент обновлен.", "success")
        return redirect(url_for("admin_content"))
    pages = query_db("SELECT * FROM site_content ORDER BY id")
    return render_template("admin/content.html", pages=pages)


@app.route("/admin/messages")
@admin_required
def admin_messages():
    messages = query_db("SELECT * FROM contacts_messages ORDER BY created_at DESC")
    return render_template("admin/messages.html", messages=messages)



def read_product_form(req) -> tuple:
    return (
        int(req.form.get("category_id")),
        req.form.get("name", "").strip(),
        req.form.get("slug", "").strip(),
        int(req.form.get("price", 0)),
        float(req.form.get("area", 0)),
        int(req.form.get("rooms", 1)),
        int(req.form.get("capacity", 1)),
        req.form.get("seasonality", "").strip(),
        req.form.get("production_time", "").strip(),
        req.form.get("short_description", "").strip(),
        req.form.get("description", "").strip(),
        req.form.get("specs", "").strip(),
        req.form.get("image_url", "").strip(),
        1 if req.form.get("is_featured") == "on" else 0,
    )


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
