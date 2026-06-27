import smtplib
from email.message import EmailMessage
from app.runtime_config import smtp_settings


def smtp_is_enabled() -> bool:
    cfg = smtp_settings(include_password=True)
    return bool(cfg.get("enabled") and cfg.get("host"))


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    cfg = smtp_settings(include_password=True)
    if not cfg.get("enabled") or not cfg.get("host"):
        raise RuntimeError("SMTP is not configured")
    msg = EmailMessage()
    from_email = cfg.get("from_email") or cfg.get("username") or "no-reply@pointless.local"
    from_name = cfg.get("from_name") or "Pointless"
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    host = cfg["host"]
    port = int(cfg.get("port") or (465 if cfg.get("use_ssl") else 587))
    username = cfg.get("username") or None
    password = cfg.get("password") or None
    if cfg.get("use_ssl"):
        server = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        server = smtplib.SMTP(host, port, timeout=20)
    try:
        if cfg.get("use_tls") and not cfg.get("use_ssl"):
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(msg)
    finally:
        server.quit()


def send_password_reset_email(to_email: str, username: str, reset_url: str) -> None:
    subject = "Reset your Pointless password"
    text = f"Hello {username},\n\nUse this link to reset your Pointless password. It expires in 1 hour:\n\n{reset_url}\n\nIf you did not request this, you can ignore this email."
    html = f"""<p>Hello {username},</p><p>Use this link to reset your Pointless password. It expires in 1 hour:</p><p><a href=\"{reset_url}\">Reset your password</a></p><p>If you did not request this, you can ignore this email.</p>"""
    send_email(to_email, subject, text, html)
