"""Optional end-to-end checks against a running CoaChess server."""
import argparse
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:5000')
parser.add_argument('--browser-executable', default=None)
args = parser.parse_args()

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=args.browser_executable, headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1280, 'height': 1000})
    errors=[]
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(args.url.rstrip('/') + '/')
    page.locator('#pgn-file').set_input_files({'name':'exemple.pgn','mimeType':'text/plain','buffer':b'1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *'})
    page.locator('#file-status').filter(has_text='Fitxer carregat').wait_for()
    assert page.locator('#pgn').input_value().startswith('1. e4')
    page.locator('#game_name').fill('Prova del navegador')
    page.locator('#time_limit').fill('0.5')
    page.locator('#multipv').fill('2')
    # Slider -> number and reset -> defaults.
    page.locator('#time_limit-slider').evaluate('(el) => { el.value = 0.8; el.dispatchEvent(new Event("input", {bubbles: true})); }')
    assert page.locator('#time_limit').input_value() == '0.8'
    page.locator('#reset-settings').click()
    assert page.locator('#time_limit').input_value() == '0.5'
    page.locator('#submit-button').click()
    page.wait_for_url('**/analysis/*')
    # Waiting is visible before any move, and the server is still responsive.
    assert page.locator('#spinner').is_visible()
    assert not page.locator('#progress').get_attribute('value') == '6'
    page.locator('.move-button').first.wait_for(timeout=20000)
    assert int(page.locator('#progress').get_attribute('value')) < 6
    assert page.locator('#position-label').inner_text() == 'Posició inicial'
    assert page.locator('#analysis-summary').is_hidden()
    page.locator('.move-button').first.click()
    page.locator('#solution').click()
    assert page.locator('#alternatives').is_visible()
    selected_image = page.locator('#board img').get_attribute('src')
    page.wait_for_function('document.getElementById("analysis-status").textContent.includes("completada")', timeout=30000)
    assert page.locator('.move-button.selected').inner_text() == 'e4'
    assert page.locator('.move-button').count() == 6
    assert page.locator('#board img').get_attribute('src') == selected_image
    assert page.locator('#alternatives').is_visible()
    assert page.locator('#analysis-summary').is_visible()
    config = page.locator('#analysis-data').evaluate('(el) => JSON.parse(el.textContent)')
    completed = page.request.get(args.url.rstrip('/') + config['statusUrl']).json()
    counts = {'best': 0, 'good': 0, 'inaccuracy': 0, 'mistake': 0, 'blunder': 0}
    for move in completed['moves']:
        if move['assessment']:
            category = move['assessment']['category']
            counts['good' if category == 'excellent' else category] += 1
    for category, count in counts.items():
        assert page.locator(f'#summary-{category}').inner_text() == str(count)
    assert page.locator('#summary-total').inner_text() == '3'
    page.locator('#final').click()
    assert page.locator('#position-label').inner_text() == 'Posició final'
    assert page.locator('#board svg').count() == 1
    page.locator('body').click(position={'x':10,'y':950})
    page.keyboard.press('ArrowLeft')
    assert 'a6' in page.locator('#position-label').inner_text()
    assert page.locator('#solution').is_disabled()
    page.keyboard.press('ArrowLeft')
    assert 'Bb5' in page.locator('#position-label').inner_text()
    page.keyboard.press('Space')
    assert page.locator('#alternatives').is_visible()
    # Responsive form and analyzed table at common phone/tablet widths.
    result_url = page.url
    responsive = browser.new_page()
    responsive.route('**/cdn.jsdelivr.net/**', lambda route: route.abort())
    responsive.on('pageerror', lambda error: errors.append(str(error)))
    for width in (320, 360, 390, 430, 768):
        responsive.set_viewport_size({'width': width, 'height': 900})
        responsive.goto(args.url.rstrip('/') + '/')
        assert responsive.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Form overflows at {width}px'
        assert responsive.locator('#time_limit').bounding_box()['height'] >= 44
        responsive.goto(result_url)
        responsive.locator('.move-button').first.wait_for()
        assert responsive.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Results overflow at {width}px'
        assert responsive.locator('#next').bounding_box()['height'] >= 44
        if width <= 430:
            assert responsive.locator('#board').bounding_box()['width'] >= width - 56
            assert responsive.locator('#next').bounding_box()['y'] > responsive.locator('#initial').bounding_box()['y']
            comment = responsive.locator('.comment-cell').first.bounding_box()
            button = responsive.locator('.move-button').first.bounding_box()
            assert comment['y'] >= button['y'] + button['height']
        assert responsive.locator('.moves-card').bounding_box()['y'] < responsive.locator('.chart-card').bounding_box()['y']
    responsive.close()
    # Mobile layout, single white ply analyzed for black, and CDN failure.
    mobile = browser.new_page(viewport={'width':390,'height':844})
    mobile.on('pageerror', lambda error: errors.append(str(error)))
    mobile.route('**/cdn.jsdelivr.net/**', lambda route: route.abort())
    mobile.goto(args.url.rstrip('/') + '/')
    mobile.locator('#pgn').fill('1. e4 *')
    mobile.locator('#player').select_option('BLACK')
    mobile.locator('#time_limit').fill('0.1')
    mobile.locator('#submit-button').click()
    mobile.wait_for_function('document.getElementById("analysis-status")?.textContent.includes("completada")', timeout=20000)
    assert mobile.locator('.move-button').count() == 1
    assert mobile.locator('#position-label').inner_text() == 'Posició inicial'
    assert mobile.locator('#summary-total').inner_text() == '0'
    assert mobile.locator('#solution').is_disabled()
    assert mobile.locator('#chart-status').is_visible()
    assert mobile.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    mobile.locator('#final').click()
    assert mobile.locator('#position-label').inner_text() == 'Posició final'
    assert not errors, errors
    print('Browser: streaming, controls, file upload, manual navigation, final board, keyboard, responsive layouts (320–768 px), mobile and CDN fallback OK')
    browser.close()
