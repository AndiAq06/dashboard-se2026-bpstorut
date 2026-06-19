import re
from bs4 import BeautifulSoup

def analyze():
    html_path = r"d:\Hamdani\scraper-fasih-sm\FASIH_ Flexible Authentic Survey Instrument in Harmony.html"
    print(f"Reading {html_path}...")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    print(f"Length of HTML content: {len(html_content)} bytes")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Check for search input
    print("\n--- Search Input Elements ---")
    inputs = soup.find_all('input')
    for i, inp in enumerate(inputs):
        print(f"Input {i}: name={inp.get('name')}, id={inp.get('id')}, class={inp.get('class')}, placeholder={inp.get('placeholder')}, type={inp.get('type')}, value={inp.get('value')}")
    
    # Check for tables
    print("\n--- Table Elements ---")
    tables = soup.find_all('table')
    print(f"Found {len(tables)} <table> tags")
    for idx, table in enumerate(tables):
        print(f"Table {idx}: class={table.get('class')}, id={table.get('id')}")
        # Print headers
        headers = [th.text.strip() for th in table.find_all('th')]
        print(f"  Headers: {headers}")
        # Print some row count
        rows = table.find_all('tr')
        print(f"  Rows count: {len(rows)}")
    
    # If no tables found, let's look for divs that might act as tables
    if not tables:
        print("\nNo <table> tags found. Looking for elements with role='table' or classes like 'table' or 'grid'...")
        table_divs = soup.find_all(lambda tag: tag.name == 'div' and (tag.get('role') == 'table' or any('table' in str(c) for c in (tag.get('class') or []))))
        print(f"Found {len(table_divs)} table-like divs")
        for idx, div in enumerate(table_divs[:5]):
            print(f"Table Div {idx}: class={div.get('class')}, id={div.get('id')}, role={div.get('role')}")
            
    # Search for pagination
    print("\n--- Pagination / Page Buttons ---")
    buttons = soup.find_all('button')
    pagination_buttons = []
    for btn in buttons:
        btn_text = btn.text.strip()
        btn_class = str(btn.get('class') or '')
        btn_id = btn.get('id') or ''
        # Look for buttons with numbers or arrows or pagination context
        if btn_text.isdigit() or any(x in btn_text.lower() for x in ['next', 'prev', 'halaman', 'page']) or any(x in btn_class.lower() for x in ['pagination', 'page']) or any(x in btn_id.lower() for x in ['pagination', 'page']):
            pagination_buttons.append(btn)
            
    print(f"Found {len(pagination_buttons)} potential pagination buttons:")
    for idx, btn in enumerate(pagination_buttons[:15]):
        print(f"Button {idx}: text='{btn.text.strip()}', id='{btn.get('id')}', class='{btn.get('class')}', attrs={ {k:v for k,v in btn.attrs.items() if k not in ['class', 'id']} }")

    # Let's search for some text in the emails to see if we can find them in the document
    print("\n--- Searching for email domains (e.g. @gmail.com) ---")
    gmail_matches = re.findall(r'[a-zA-Z0-9._%+-]+@gmail\.com', html_content)
    print(f"Total gmail matches in text: {len(gmail_matches)}")
    unique_gmails = set(gmail_matches)
    print(f"Unique gmail addresses found: {list(unique_gmails)[:10]}")
    
    # If there are matching emails, find where they are in the DOM
    if unique_gmails:
        sample_email = list(unique_gmails)[0]
        print(f"\nLocating sample email '{sample_email}' in DOM:")
        elements = soup.find_all(string=re.compile(sample_email))
        for el in elements[:5]:
            parent = el.parent
            print(f"Found in text child of parent: {parent.name}, class={parent.get('class')}, id={parent.get('id')}, text='{parent.text.strip()[:100]}'")
            # Show parent's parent
            if parent.parent:
                print(f"  Parent's parent: {parent.parent.name}, class={parent.parent.get('class')}, id={parent.parent.get('id')}")

if __name__ == "__main__":
    analyze()
