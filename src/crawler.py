import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Dict
import re
import certifi
import time
import os

class WebsiteCrawler:
    def __init__(self, use_selenium: bool = False):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.use_selenium = use_selenium
        self.debug_html = None  # Store for debugging
    
    def validate_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except:
            return False
    
    def fetch_with_selenium(self, url: str) -> str:
        """Fetch with undetected-chromedriver to bypass anti-bot"""
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            options = uc.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-gpu')
            
            driver = uc.Chrome(options=options)
            
            try:
                driver.get(url)
                
                # Wait for article content specifically
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "article"))
                )
                
                # Multiple scrolls to load lazy content
                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                
                html = driver.page_source
                self.debug_html = html[:2000]  # Store first 2000 chars for debug
                
                # Save full HTML for debugging
                debug_path = os.path.join(os.getcwd(), "debug_last_fetch.html")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(html)
                
                return html
                
            finally:
                driver.quit()
                
        except Exception as e:
            # Fallback to regular selenium if undetected fails
            return self.fallback_selenium(url)
    
    def fallback_selenium(self, url: str) -> str:
        """Regular selenium with stealth options"""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # Remove webdriver property to avoid detection
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        try:
            driver.get(url)
            time.sleep(5)  # Simple wait
            
            # Scroll
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            html = driver.page_source
            
            # Save debug
            with open("debug_last_fetch.html", "w", encoding="utf-8") as f:
                f.write(html)
            
            return html
        finally:
            driver.quit()
    
    def fetch_content(self, url: str) -> Dict:
        if not self.validate_url(url):
            return {'success': False, 'error': 'Invalid URL format'}
        
        html = None
        used_selenium = False
        
        try:
            # Try requests first if not forcing selenium
            if not self.use_selenium:
                response = self.session.get(url, timeout=15, verify=certifi.where())
                response.raise_for_status()
                html = response.text
                
                # Check length
                test_soup = BeautifulSoup(html, 'lxml')
                if len(test_soup.get_text(strip=True)) < 500:
                    return {
                        'success': False, 
                        'error': 'Content too short. Enable "Use JavaScript Rendering" for this site.'
                    }
            else:
                # Use Selenium with anti-detection
                html = self.fetch_with_selenium(url)
                used_selenium = True
            
            soup = BeautifulSoup(html, 'lxml')
            title = soup.title.string.strip() if soup.title else "Untitled"
            
            # Remove unwanted tags
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 
                           'aside', 'form', 'button', 'iframe', 'noscript']):
                tag.decompose()
            
            # GeeksforGeeks specific selectors
            gfg_selectors = [
                'div.content', 'div.article-content', 'div.entry-content',
                'article', 'main', '.post-content', '.entry-content',
                '[itemprop="articleBody"]', '#content'
            ]
            
            content_area = None
            for selector in gfg_selectors:
                if selector.startswith('.'):
                    content_area = soup.find(class_=selector[1:])
                elif selector.startswith('#'):
                    content_area = soup.find(id=selector[1:])
                elif selector.startswith('['):
                    key, val = selector[1:-1].split('=')
                    content_area = soup.find(attrs={key: val.strip('"')})
                else:
                    content_area = soup.find(selector)
                
                if content_area:
                    break
            
            # Fallback to body if nothing found
            if not content_area:
                content_area = soup.find('body')
            
            if not content_area:
                return {'success': False, 'error': 'No content area found'}
            
            # Get text
            text = content_area.get_text(separator='\n', strip=True)
            
            # Clean lines
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n\n'.join(lines)
            
            if len(text) < 100:
                # Show debug info
                error_msg = f'Content too short ({len(text)} chars). '
                if os.path.exists("debug_last_fetch.html"):
                    error_msg += 'Check debug_last_fetch.html saved in app folder.'
                return {'success': False, 'error': error_msg}
            
            return {
                'success': True,
                'url': url,
                'title': title,
                'content': text,
                'length': len(text),
                'method': 'selenium' if used_selenium else 'requests'
            }
            
        except Exception as e:
            import traceback
            return {
                'success': False, 
                'error': f'{str(e)}\n{traceback.format_exc()[:200]}'
            }