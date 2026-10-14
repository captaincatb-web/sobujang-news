import smtplib
from email.mime.text import MIMEText


def send_html(smtp_host: str, smtp_port: int, user: str, password: str, to: str, subject: str, html_body: str) -> None:
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to

    with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
        server.login(user, password)
        server.sendmail(user, [addr.strip() for addr in to.split(",")], msg.as_string())
