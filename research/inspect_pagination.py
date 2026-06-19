from bs4 import BeautifulSoup

def inspect_pagination():
    html_path = r"d:\Hamdani\scraper-fasih-sm\FASIH_ Flexible Authentic Survey Instrument in Harmony.html"
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Let's find the table element first, and see what elements exist around or below it
    table = soup.find('table')
    if not table:
        print("Table not found")
        return
        
    print("Table found. Now finding siblings or elements below the table container.")
    
    # Let's find all buttons and print their inner elements, text, and attributes
    print("\n--- All Buttons in the Page ---")
    buttons = soup.find_all('button')
    for idx, btn in enumerate(buttons):
        # get text
        btn_text = btn.text.strip()
        # check if it has SVGs
        svgs = btn.find_all('svg')
        svg_classes = [svg.get('class') for svg in svgs]
        print(f"Button {idx}: text='{btn_text}', class={btn.get('class')}, id={btn.get('id')}, svgs_count={len(svgs)}, svg_classes={svg_classes}, disabled={btn.has_attr('disabled')}")
        
    # Let's find elements that look like pagination container (often has class containing 'pagination', 'flex', etc.)
    # typically placed after the table
    print("\n--- HTML structure after the table ---")
    parent = table.parent
    # Let's see parents of table
    p = table
    depth = 0
    while p and depth < 3:
        p = p.parent
        print(f"Parent at depth {depth+1}: tag={p.name}, class={p.get('class')}, id={p.get('id')}")
        depth += 1

if __name__ == "__main__":
    inspect_pagination()
