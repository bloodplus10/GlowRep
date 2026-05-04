import re

def is_valid_price(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False

def contains_banned_words(text: str, banned_words: list) -> bool:
    text_lower = text.lower()
    for word in banned_words:
        if word in text_lower:
            return True
    return False

def contains_url(text: str) -> bool:
    url_pattern = r'https?://\S+|www\.\S+'
    return bool(re.search(url_pattern, text))
