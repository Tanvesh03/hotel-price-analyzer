import asyncio
import re
from datetime import date, timedelta
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper

HOTEL_SLUGS = {
      1: "stayvista-at-kuhu-natures-retreat",
      2: "sea-horizon-luxury-villas-mandrem-beach-goa",
      3: "baia-villas-mandrem",
      4: "stone-wood-resort-mandrem",
      5: "mandrem-retreat-beach-resort",
      6: "aroha-palms-mandrem-luxury-villas",
      7: "rainforest-floresta",
      8: "amoravida-7-apple-resorts",
}

class BookingScraper(BaseScraper):
      BASE = "https://www.booking.com/hotel/in/{slug}.en-gb.html"

    def build_url(self, slug, checkin, nights=1):
              co = checkin + timedelta(days=nights)
              return (f"{self.BASE.format(slug=slug)}"
                      f"?checkin={checkin}&checkout={co}"
                      f"&group_adults=2&no_rooms=1&sb_price_type=total&currency=INR")

    def parse(self, html, slug, checkin, property_id):
              soup = BeautifulSoup(html, "lxml")
              r = {"property_id": property_id, "ota": "booking",
                   "hotel_slug": slug, "checkin_date": str(checkin),
                   "checkout_date": str(checkin + timedelta(days=1)),
                   "base_price": None, "taxes": None, "final_price": None,
                   "room_type": None, "meal_plan": "RO", "is_refundable": False,
                   "cancellation_policy": None, "availability": None, "promo_applied": False}
              try:
                            p = soup.select_one('[data-testid="price-and-discounted-price"]') or soup.select_one('.bui-price-display__value')
                            if p:
                                              nums = re.findall(r'\d+', p.get_text().replace(',',''))
                                              if nums: r['final_price'] = float(nums[-1])
                                                            t = soup.select_one('[data-testid="taxes-and-charges"]')
                                          if t:
                                                            nums = re.findall(r'\d+', t.get_text().replace(',',''))
                                                            r['taxes'] = float(nums[0]) if nums else 0.0
                                                            if r['final_price'] and r['taxes']:
                                                                                  r['base_price'] = r['final_price'] - r['taxes']
                                                                          c = soup.select_one('[data-testid="cancellation-policy"]')
                                                        if c:
                                                                          txt = c.get_text().lower()
                                                                          r['is_refundable'] = 'free cancellation' in txt or 'refundable' in txt
                                                                          r['cancellation_policy'] = c.get_text(strip=True)[:200]
                                                                      rm = soup.select_one('[data-testid="roomtype-title"]') or soup.select_one('.room-type-name')
                            if rm: r['room_type'] = rm.get_text(strip=True)[:100]
                                          ml = soup.select_one('[data-testid="breakfast-info"]')
                            if ml:
                                              m = ml.get_text().lower()
                                              r['meal_plan'] = 'BB' if 'breakfast' in m else 'HB' if 'half board' in m else 'RO'
                                          av = soup.select_one('[data-testid="availability-count"]')
                            if av:
                                              n = re.findall(r'\d+', av.get_text())
                                              r['availability'] = int(n[0]) if n else None
                                          if soup.select_one('[data-testid="discount-badge"]'):
                                                            r['promo_applied'] = True
              except Exception as e:
                            self.logger.error(f"Parse error {slug}: {e}")
                        return r

    async def scrape(self, property_id, checkin):
              slug = HOTEL_SLUGS.get(property_id)
        if not slug:
                      raise ValueError(f"Unknown property_id: {property_id}")
                  url = self.build_url(slug, checkin)
        html = await self.get_page_html(url, wait_selector='[data-testid="price-and-discounted-price"]')
        return self.parse(html, slug, checkin, property_id)

    async def scrape_all(self, checkin):
              tasks = [self.scrape(pid, checkin) for pid in HOTEL_SLUGS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]
