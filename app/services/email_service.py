import html
import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any, Dict, List, Optional


def send_doi_email(
    to_email: str,
    records: List[Dict[str, Any]],
    sender_display: Optional[str] = None
) -> tuple[bool, str]:
    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT", "587"))
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")
    sender_addr = os.getenv("EMAIL_FROM") or user
    default_name = os.getenv("EMAIL_SENDER_NAME", "paperscout")
    use_tls = os.getenv("EMAIL_USE_TLS", "true").lower() in ("1","true","yes","y")
    use_ssl = os.getenv("EMAIL_USE_SSL", "false").lower() in ("1","true","yes","y")

    if not (host and port and sender_addr and user and password):
        return False, "SMTP nicht konfiguriert."

    display_name = (sender_display or "").strip() or default_name

    # --- HTML Tabellen-Inhalt generieren (modernes Design) ---
    table_rows = ""
    for i, rec in enumerate(records):
        title = html.escape(str(rec.get("title", "(ohne Titel)")))
        authors = html.escape(str(rec.get("authors", "Autor:innen unbekannt")))
        journal = html.escape(str(rec.get("journal", "Journal unbekannt")))
        issued = html.escape(str(rec.get("issued", "")))
        doi_url = str(rec.get("doi", ""))
        
        table_rows += f"""
        <tr>
            <td style="padding: 10px 0;">
                <div style="border:1px solid #e7e7ec; border-radius:14px; padding:16px; background:#ffffff;">
                    <div style="font-weight:700; color:#101217; font-size:16px; margin-bottom:6px;">{title}</div>
                    <div style="font-size:13px; color:#3a3f4b; margin-bottom:8px;">{authors}</div>
                    <div style="font-size:12px; color:#6a7282; margin-bottom:12px;">
                        <span style="font-weight:600;">{journal}</span> {f'· {issued}' if issued else ''}
                    </div>
                    <a href="{doi_url}" style="display:inline-block; padding:8px 12px; border-radius:999px; background:#ff6b35; color:#ffffff; text-decoration:none; font-size:12px; font-weight:700;">
                        DOI öffnen
                    </a>
                </div>
            </td>
        </tr>
        """

    # --- Das HTML-Template ---
    html_body = f"""
    <html>
    <body style="margin:0; padding:0; background:#f7f3ef; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color:#101217;">
        <div style="max-width: 720px; margin: 24px auto; padding: 0 16px;">
            <div style="border-radius: 18px; overflow: hidden; border:1px solid #e7e7ec; background:#ffffff;">
                <div style="padding: 20px; background: linear-gradient(135deg, #ff6b35, #ff9f2e); color: #ffffff;">
                    <div style="font-size: 20px; font-weight: 800; letter-spacing:-0.02em;">paperscout</div>
                    <div style="font-size: 12px; opacity:0.9;">Research Digest · {len(records)} Artikel</div>
                </div>
                <div style="padding: 20px;">
                    <p style="margin:0 0 10px 0;">Hallo,</p>
                    <p style="margin:0 0 14px 0; color:#3a3f4b;">
                        hier ist deine kuratierte Übersicht der ausgewählten Artikel.
                    </p>
                    <div style="font-size:12px; color:#6a7282; margin-bottom:12px;">
                        Ausgewählt von: <strong>{display_name}</strong>
                    </div>
                    <table style="width:100%; border-collapse: collapse;">
                        {table_rows}
                    </table>
                    <div style="margin-top: 18px; padding-top: 14px; border-top: 1px solid #eeeeee; font-size: 11px; color: #8b92a1;">
                        Gesendet via paperscout · {datetime.now().strftime('%d.%m.%Y %H:%M')}
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[paperscout] {len(records)} Artikel — {display_name}"
    msg["From"] = formataddr((display_name, sender_addr))
    msg["To"] = to_email
    text_fallback = f"Hallo,\n\nhier sind {len(records)} Artikel für dich.\n(Bitte HTML-Ansicht aktivieren für das volle Design.)"
    msg.attach(MIMEText(text_fallback, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as server:
                server.login(user, password)
                server.sendmail(sender_addr, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(host, port) as server:
                server.ehlo()
                if use_tls: server.starttls(context=ssl.create_default_context()); server.ehlo()
                server.login(user, password)
                server.sendmail(sender_addr, [to_email], msg.as_string())
        return True, "E-Mail mit neuem Design gesendet."
    except Exception as e: return False, f"E-Mail Versand fehlgeschlagen: {e}"