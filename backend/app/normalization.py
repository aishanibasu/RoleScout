"""Shared text and geographic normalization for public career sources."""
import html
import re
from html.parser import HTMLParser

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'li', 'br', 'h2', 'h3', 'h4'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('p', 'li', 'h2', 'h3', 'h4'):
            self.parts.append('\n')

def plain(value):
    parser = TextParser()
    parser.feed(html.unescape(value or ''))
    return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())

def decode_js_string(value):
    def decode(m):
        token = m.group(1)
        if token.startswith('u') and len(token) == 5:
            return chr(int(token[1:], 16))
        if token.startswith('x') and len(token) == 3:
            return chr(int(token[1:], 16))
        return {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f'}.get(token, token)
    return re.sub(r'\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)', decode, value)

CITY_MAP = {
    'new york': ('New York City', 'New York', 'United States'),
    'new york city': ('New York City', 'New York', 'United States'),
    'stamford': ('Stamford', 'Connecticut', 'United States'),
    'chicago': ('Chicago', 'Illinois', 'United States'),
    'san francisco': ('San Francisco', 'California', 'United States'),
    'miami': ('Miami', 'Florida', 'United States'),
    'boston': ('Boston', 'Massachusetts', 'United States'),
    'palo alto': ('Palo Alto', 'California', 'United States'),
    'london': ('London', 'England', 'United Kingdom'),
    'warsaw': ('Warsaw', 'Mazovia', 'Poland'),
    'paris': ('Paris', 'Île-de-France', 'France'),
    'tokyo': ('Tokyo', 'Tokyo', 'Japan'),
    'singapore': ('Singapore', '', 'Singapore'),
    'hong kong': ('Hong Kong', '', 'Hong Kong'),
    'sydney': ('Sydney', 'New South Wales', 'Australia'),
    'dubai': ('Dubai', 'Dubai', 'United Arab Emirates'),
}

def locations(raw):
    result = []
    for piece in re.split(r'\s*[|;]\s*', raw or ''):
        city = piece.split(',')[0].strip()
        if not city:
            continue
        mapped = CITY_MAP.get(city.lower(), (city, '', ''))
        result.append(dict(zip(('city', 'region', 'country'), mapped), raw=piece))
    return result

