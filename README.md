# Excellent Star Signs & Bea Ads — Website

Flask + SQLite company website for two sister businesses, with a public catalogue
(no login required) and an admin panel (login required) to manage everything.

## Setup

```
pip install -r requirements.txt
python app.py
```

Visit `http://127.0.0.1:5000/` for the public site.
Visit `http://127.0.0.1:5000/admin/login` for the admin panel (or click
"Staff Access" in the site footer).

The database (`instance/store.db`) and a default Super Admin are created
automatically on first run, along with the starter categories from the brief.

**Default Super Admin login:** `excellentstarsigns@gmail.com` / `excellent686`
You can change these from **My Account** in the admin panel after logging in.

## What's included

### Public site (no login needed)
- Hero with a rotating slideshow of up to 5 admin-picked gallery photos
- Flat sidebar of categories (no company grouping)
- Product/service grid with optional price and description
- Service detail pages
- **Gallery** — completed work showcase, grouped by category
- **Contact page** — phone, landline, email, address, business hours, social
  links, and an embedded Google Map (if configured)
- "Get a Quote" / "Enquire" forms — only Name and Phone are required; Email
  and Message are optional
- "Staff Access" link in the footer leads to the admin login (no public
  "Admin" button in the header)

### Admin panel (`/admin`, or via "Staff Access" in the site footer)
- **Categories** — add/edit/delete, optional company tag
- **Services** — add/edit/delete, with image, optional price, optional
  description, optional badge, optional company tag
- **Gallery** — upload/edit/delete completed-work images, optional category.
  Mark up to 5 images as "Feature in Hero" — these rotate as a slideshow on
  the homepage hero. Attempting to feature a 6th shows a warning instead of
  silently failing.
- **Banners** — upload/hide/delete promotional images (legacy section, kept
  for future use; the homepage hero itself now pulls from featured Gallery
  images instead)
- **Enquiries** — view, mark as contacted, delete
- **Settings** — phone numbers, landline, email, address, business hours,
  Google Maps embed URL, social links, site title/tagline
- **Sub Admins** (Super Admin only) — add/edit/delete sub admin accounts,
  with per-permission checkboxes (Services, Categories, Images, Contacts,
  Enquiries)
- **My Account** (Super Admin only) — change the Super Admin's own
  email/password

## Admin roles

- **Super Admin**: full access to everything, including managing Sub Admins.
  There is exactly one Super Admin account.
- **Sub Admin**: access only to the sections the Super Admin has checked off
  for them (Services / Categories / Images / Contacts / Enquiries). Sub
  Admins cannot see or manage other Sub Admins or the Super Admin's own
  credentials — those routes are locked to the Super Admin only, even by
  direct URL.

## Notes

- Images are saved under `static/uploads/` and referenced by path in the database.
- The site logo is `static/uploads/logo.png` — replace this single file to
  update the logo everywhere (header, admin login, admin sidebar) without
  touching any template.
- Deleting a category deletes its services (cascade). Services are not
  required to have a company tag — it's optional metadata, not a structural
  grouping.
- This uses Flask's built-in dev server (`python app.py`). For real
  deployment, run it behind a production WSGI server (e.g. gunicorn) and set
  a proper, secret `app.secret_key` (currently a placeholder in `app.py`).
