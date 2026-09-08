BANNED_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "aol.com",
    "icloud.com",
    "mail.com",
    "inbox.com",
    "live.com",
    "msn.com",
    "yopmail.com",
    "mailinator.com",
    "tempmail.com",
    "guerrillamail.com",
    "10minutemail.com",
    "throwawaymail.com",
    "disposableemail.com",
    "deletedemail.com",
    "trashmail.com",
    "maildrop.cc",
    "temp-mail.org",
    "tempinbox.com",
    "tempmailbox.com",
    "tempmail.io",
    "tempmail.cc",
    "tempmail.net",
    "tempmail.org",
}


def extract_domain(email: str) -> str:
    return email.split("@")[1].lower().strip()


def is_banned_email_domain(domain: str) -> bool:
    return domain in BANNED_EMAIL_DOMAINS