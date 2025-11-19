from dotenv import load_dotenv
import asyncio
import os
import re
from urllib.parse import urljoin, urlparse
from pathlib import Path
import aiohttp
import json
from playwright.async_api import async_playwright

load_dotenv()

class WebCloner:
    def __init__(self, url, output_dir="cloned_site"):
        self.url = url
        self.output_dir = output_dir
        self.domain = urlparse(url).netloc
        self.assets = {
            'css': [],
            'js': [],
            'images': [],
            'fonts': [],
            'svgs': []
        }

    async def setup_directories(self):
        """Create directory structure for cloned site"""
        directories = [
            self.output_dir,
            f"{self.output_dir}/css",
            f"{self.output_dir}/js",
            f"{self.output_dir}/images",
            f"{self.output_dir}/fonts",
            f"{self.output_dir}/svgs",
            f"{self.output_dir}/screenshots"
        ]
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory structure in {self.output_dir}/")

    async def download_file(self, url, filepath):
        """Download a file from URL and save it"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(filepath, 'wb') as f:
                            f.write(content)
                        return True
        except Exception as e:
            print(f"⚠️  Error downloading {url}: {str(e)}")
            return False

    async def extract_assets_from_page(self, page):
        """Extract all asset URLs from the page"""
        print("\n🔍 Extracting assets from page...")

        # Get all stylesheets
        css_links = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('link[rel="stylesheet"]'))
                .map(link => link.href);
        }""")
        self.assets['css'].extend(css_links)

        # Get all scripts
        js_links = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('script[src]'))
                .map(script => script.src);
        }""")
        self.assets['js'].extend(js_links)

        # Get all images
        image_links = await page.evaluate(r"""() => {
            const images = Array.from(document.querySelectorAll('img[src]'))
                .map(img => img.src);
            const bgImages = Array.from(document.querySelectorAll('*'))
                .map(el => {
                    const bg = window.getComputedStyle(el).backgroundImage;
                    const match = bg.match(/url\(['"]?([^'"]+)['"]?\)/);
                    return match ? match[1] : null;
                })
                .filter(url => url && url.startsWith('http'));
            return [...images, ...bgImages];
        }""")
        self.assets['images'].extend(image_links)

        # Get all SVGs (inline and external)
        svg_links = await page.evaluate("""() => {
            const svgImages = Array.from(document.querySelectorAll('img[src$=".svg"], img[src*=".svg?"]'))
                .map(img => img.src);
            const svgObjects = Array.from(document.querySelectorAll('object[type="image/svg+xml"]'))
                .map(obj => obj.data);
            return [...svgImages, ...svgObjects];
        }""")
        self.assets['svgs'].extend(svg_links)

        # Extract fonts from CSS
        all_fonts = await page.evaluate(r"""() => {
            const fonts = [];
            for (const sheet of document.styleSheets) {
                try {
                    for (const rule of sheet.cssRules) {
                        if (rule instanceof CSSFontFaceRule) {
                            const src = rule.style.getPropertyValue('src');
                            const urls = src.match(/url\(['"]?([^'"]+)['"]?\)/g);
                            if (urls) {
                                urls.forEach(url => {
                                    const match = url.match(/url\(['"]?([^'"]+)['"]?\)/);
                                    if (match) fonts.push(match[1]);
                                });
                            }
                        }
                    }
                } catch (e) {}
            }
            return fonts;
        }""")

        # Convert relative font URLs to absolute
        for font_url in all_fonts:
            if font_url.startswith('http'):
                self.assets['fonts'].append(font_url)
            else:
                self.assets['fonts'].append(urljoin(self.url, font_url))

        # Remove duplicates
        for key in self.assets:
            self.assets[key] = list(set(self.assets[key]))

        print(f"✅ Found {len(self.assets['css'])} CSS files")
        print(f"✅ Found {len(self.assets['js'])} JS files")
        print(f"✅ Found {len(self.assets['images'])} images")
        print(f"✅ Found {len(self.assets['fonts'])} fonts")
        print(f"✅ Found {len(self.assets['svgs'])} SVGs")

    async def download_assets(self):
        """Download all extracted assets"""
        print("\n📥 Downloading assets...")

        # Download CSS
        for i, css_url in enumerate(self.assets['css']):
            filename = f"style_{i}.css"
            filepath = f"{self.output_dir}/css/{filename}"
            if await self.download_file(css_url, filepath):
                print(f"✅ Downloaded CSS: {filename}")

        # Download JS
        for i, js_url in enumerate(self.assets['js']):
            filename = f"script_{i}.js"
            filepath = f"{self.output_dir}/js/{filename}"
            if await self.download_file(js_url, filepath):
                print(f"✅ Downloaded JS: {filename}")

        # Download Images
        for i, img_url in enumerate(self.assets['images']):
            ext = Path(urlparse(img_url).path).suffix or '.jpg'
            filename = f"image_{i}{ext}"
            filepath = f"{self.output_dir}/images/{filename}"
            if await self.download_file(img_url, filepath):
                print(f"✅ Downloaded Image: {filename}")

        # Download SVGs
        for i, svg_url in enumerate(self.assets['svgs']):
            filename = f"svg_{i}.svg"
            filepath = f"{self.output_dir}/svgs/{filename}"
            if await self.download_file(svg_url, filepath):
                print(f"✅ Downloaded SVG: {filename}")

        # Download Fonts
        for i, font_url in enumerate(self.assets['fonts']):
            ext = Path(urlparse(font_url).path).suffix or '.woff2'
            filename = f"font_{i}{ext}"
            filepath = f"{self.output_dir}/fonts/{filename}"
            if await self.download_file(font_url, filepath):
                print(f"✅ Downloaded Font: {filename}")

    async def save_html(self, page):
        """Save the HTML DOM"""
        print("\n📄 Saving HTML...")
        html_content = await page.content()
        with open(f"{self.output_dir}/index.html", 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ Saved HTML to {self.output_dir}/index.html")

    async def scroll_page_fully(self, page):
        """Scroll through entire page to trigger lazy-loaded content"""
        print("🔄 Scrolling through page to load lazy content...")

        # Get total page height
        total_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = await page.evaluate("window.innerHeight")

        # Scroll down in steps
        current_position = 0
        scroll_step = viewport_height

        while current_position < total_height:
            await page.evaluate(f"window.scrollTo(0, {current_position})")
            await asyncio.sleep(0.5)  # Wait for lazy load
            current_position += scroll_step

            # Update total height in case new content loaded
            total_height = await page.evaluate("document.body.scrollHeight")

        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)
        print("✅ Finished scrolling through page")

    async def wait_for_images_and_fonts(self, page):
        """Wait for all images and fonts to load"""
        print("⏳ Waiting for all images and fonts to load...")

        # Wait for all images to load
        await page.evaluate("""
            () => {
                return Promise.all(
                    Array.from(document.images)
                        .filter(img => !img.complete)
                        .map(img => new Promise(resolve => {
                            img.onload = img.onerror = resolve;
                        }))
                );
            }
        """)

        # Wait for fonts to load
        await page.evaluate("document.fonts.ready")

        # Additional wait for any background images or late-loading content
        await asyncio.sleep(2)
        print("✅ All images and fonts loaded")

    async def take_screenshots(self, page):
        """Take screenshots of the page"""
        print("\n📸 Taking screenshots...")

        # Scroll through page to load lazy content
        await self.scroll_page_fully(page)

        # Wait for all content to load
        await self.wait_for_images_and_fonts(page)

        # Full page screenshot
        await page.screenshot(
            path=f"{self.output_dir}/screenshots/fullpage.png",
            full_page=True
        )
        print(f"✅ Saved full page screenshot")

        # Viewport screenshot
        await page.screenshot(
            path=f"{self.output_dir}/screenshots/viewport.png"
        )
        print(f"✅ Saved viewport screenshot")

    async def save_metadata(self):
        """Save metadata about the cloned site"""
        metadata = {
            'url': self.url,
            'domain': self.domain,
            'assets': {
                'css_count': len(self.assets['css']),
                'js_count': len(self.assets['js']),
                'images_count': len(self.assets['images']),
                'fonts_count': len(self.assets['fonts']),
                'svgs_count': len(self.assets['svgs'])
            },
            'asset_urls': self.assets
        }

        with open(f"{self.output_dir}/metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        print(f"✅ Saved metadata to {self.output_dir}/metadata.json")

    async def clone(self):
        """Main cloning process"""
        print(f"\n🚀 Starting web cloning for: {self.url}\n")

        # Setup directories
        await self.setup_directories()

        async with async_playwright() as p:
            try:
                print(f"🌐 Navigating to {self.url}...")

                # Launch browser with larger viewport
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = await context.new_page()

                # Navigate to URL and wait for network to be idle
                await page.goto(self.url, wait_until='networkidle', timeout=60000)
                print("✅ Initial page load complete")

                # Wait for document ready state
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_load_state('load')

                # Wait for dynamic content (React/Vue/Angular to render)
                await asyncio.sleep(3)

                # Try to close cookie popups
                try:
                    # Common cookie button selectors
                    cookie_selectors = [
                        'text=/accept all/i',
                        'text=/accept/i',
                        'button:has-text("Accept")',
                        'button:has-text("Accept All")',
                        '[class*="accept"]',
                        '[id*="accept"]'
                    ]
                    for selector in cookie_selectors:
                        try:
                            await page.click(selector, timeout=1000)
                            await asyncio.sleep(1)
                            print("✅ Closed cookie popup")
                            break
                        except:
                            continue
                except:
                    pass

                # Wait a bit more for any post-interaction content
                await asyncio.sleep(2)

                print("✅ Page loaded successfully")

                # Extract and download all assets
                await self.extract_assets_from_page(page)
                await self.download_assets()

                # Save HTML
                await self.save_html(page)

                # Take screenshots
                await self.take_screenshots(page)

                # Save metadata
                await self.save_metadata()

                print(f"\n✅ Web cloning completed! All files saved to: {self.output_dir}/")

                # Close browser
                await browser.close()

            except Exception as e:
                print(f"❌ Error during cloning: {str(e)}")
                import traceback
                traceback.print_exc()

async def main():
    # Get URL from user (you can modify this to accept command line args)
    url = input("Enter the URL to clone: ").strip()

    if not url.startswith('http'):
        url = 'https://' + url

    # Create a safe directory name from URL
    domain = urlparse(url).netloc.replace('.', '_')
    output_dir = f"cloned_{domain}"

    # Initialize and run cloner
    cloner = WebCloner(url, output_dir)
    await cloner.clone()

if __name__ == "__main__":
    asyncio.run(main())
