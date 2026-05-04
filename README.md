# OmniFlow-WMS (Enterprise Edition)

> **Legal Notice:** This repository is not open source. It is published strictly as a technical portfolio to demonstrate architectural and development skills. Commercial use, deployment, or modification is prohibited without explicit permission. Please refer to the `LICENSE` file for details.

A production-ready Warehouse Management System designed for enterprise environments. It features a scalable architecture, robust security, and high performance for tracking inventory, processing orders, and managing warehouse operations.

## Features

- **Multi-Tenant Architecture**: Supports isolated database instances per client to ensure strict data separation.
- **Security-First Approach**:
  - Comprehensive SQL injection protection via parameterized queries.
  - Active CSRF protection analyzing Origin and Referer headers.
  - Enforcement of Secure HTTP Headers (Strict-Transport-Security, X-Frame-Options, Content-Security-Policy).
- **High Performance**: Optimized SQLite database operations with targeted indices for frequent querying operations, maintaining low latency even with large datasets.
- **Customizable Environment**: Dynamic configuration for schedules, shifts, branding, and breaks directly from the UI.

## Installation and Deployment

1. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the application (Production Mode):**
   ```bash
   set FLASK_ENV=production
   waitress-serve --port=5000 app:app
   ```
   *(Note: The database `bodega.db` and the default admin user will be initialized automatically on the first startup).*

## Technical Stack

- **Backend**: Python, Flask
- **Database**: SQLite (Designed for easy migration to PostgreSQL)
- **Frontend**: Vanilla HTML/JS/CSS, Jinja2 Templates
