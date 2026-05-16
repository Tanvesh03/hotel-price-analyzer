import sqlite3
import pandas as pd
from pathlib import Path
from contextlib import contextmanager
from loguru import logger


DB_PATH = Path("database/price_data.db")
SCHEMA_PATH = Path("database/schema.sql")


class DBManager:
      def __init__(self):
                DB_PATH.parent.mkdir(exist_ok=True)
                self._init_db()

      @contextmanager
      def conn(self):
                c = sqlite3.connect(DB_PATH)
                c.row_factory = sqlite3.Row
                try:
                              yield c
                              c.commit()
except Exception as e:
            c.rollback()
            logger.error(f"DB error: {e}")
            raise
finally:
            c.close()

    def _init_db(self):
              if SCHEMA_PATH.exists():
                            with open(SCHEMA_PATH) as f:
                                              schema = f.read()
                                          with self.conn() as c:
                                                            c.executescript(schema)
                                                        logger.info("DB initialized")

          # ── INSERT ─────────────────────────────────────────────
          def insert_price(self, data: dict):
                    sql = """INSERT INTO price_snapshots
                                (property_id, ota, checkin_date, checkout_date, room_type,
                                             meal_plan, base_price, taxes, final_price, is_refundable,
                                                          cancellation_policy, availability, promo_applied)
                                                                      VALUES (:property_id,:ota,:checkin_date,:checkout_date,:room_type,
                                                                                          :meal_plan,:base_price,:taxes,:final_price,:is_refundable,
                                                                                                              :cancellation_policy,:availability,:promo_applied)"""
                    with self.conn() as c:
                                  c.execute(sql, data)

                def insert_parity(self, data: dict):
                          sql = """INSERT INTO parity_snapshots
                                      (checkin_date, booking_price, agoda_price, mmt_price,
                                                   goibibo_price, expedia_price, stayvista_price,
                                                                lowest_ota, highest_ota, min_price, max_price,
                                                                             avg_price, parity_variance_pct, parity_status)
                                                                                         VALUES (:checkin_date,:booking_price,:agoda_price,:mmt_price,
                                                                                                             :goibibo_price,:expedia_price,:stayvista_price,
                                                                                                                                 :lowest_ota,:highest_ota,:min_price,:max_price,
                                                                                                                                                     :avg_price,:parity_variance_pct,:parity_status)"""
                          with self.conn() as c:
                                        c.execute(sql, data)

                      def insert_alert(self, data: dict):
                                sql = """INSERT INTO alerts
                                            (alert_type, property_id, ota, checkin_date, message, severity)
                                                        VALUES (:alert_type,:property_id,:ota,:checkin_date,:message,:severity)"""
                                with self.conn() as c:
                                              c.execute(sql, data)

                            def upsert_competitor_price(self, data: dict):
                                      sql = """INSERT OR REPLACE INTO competitor_pricing
                                                  (property_id, checkin_date, ota, final_price, room_type, meal_plan,
                                                               is_refundable, review_score)
                                                                           VALUES (:property_id,:checkin_date,:ota,:final_price,:room_type,
                                                                                               :meal_plan,:is_refundable,:review_score)"""
                                      with self.conn() as c:
                                                    c.execute(sql, data)

    # ── SELECT ─────────────────────────────────────────────
    def get_parity_last_n_days(self, n=7) -> pd.DataFrame:
              with self.conn() as c:
                            return pd.read_sql(
                                              f"SELECT * FROM parity_snapshots ORDER BY checkin_date ASC LIMIT {n}", c)

          def get_competitor_prices(self, days=7) -> pd.DataFrame:
                    with self.conn() as c:
                                  return pd.read_sql("""
                                                  SELECT p.name, p.distance_km, p.star_rating, p.review_score as prop_score,
                                                                         cp.ota, cp.room_type, cp.meal_plan, cp.is_refundable,
                                                                                                cp.final_price, cp.checkin_date, cp.review_score
                                                                                                                FROM competitor_pricing cp
                                                                                                                                JOIN properties p ON cp.property_id = p.id
                                                                                                                                                WHERE p.type != 'my_hotel'
                                                                                                                                                                ORDER BY cp.checkin_date ASC, cp.final_price ASC""", c)

    def get_my_hotel_prices(self, days=7) -> pd.DataFrame:
              with self.conn() as c:
                            return pd.read_sql("""
                                            SELECT ps.*, p.name FROM price_snapshots ps
                                                            JOIN properties p ON ps.property_id = p.id
                                                                            WHERE p.type = 'my_hotel'
                                                                                            ORDER BY checkin_date ASC LIMIT ?""", c, params=(days,))

          def get_open_alerts(self) -> pd.DataFrame:
                    with self.conn() as c:
                                  return pd.read_sql(
                                                    "SELECT * FROM alerts WHERE is_resolved=0 ORDER BY created_at DESC LIMIT 20", c)

                def get_all_properties(self) -> pd.DataFrame:
                          with self.conn() as c:
                                        return pd.read_sql("SELECT * FROM properties ORDER BY distance_km", c)

                      def get_price_trend(self, property_id: int, days: int = 30) -> pd.DataFrame:
                                with self.conn() as c:
                                              return pd.read_sql("""
                                                              SELECT checkin_date, ota, final_price, room_type
                                                                              FROM price_snapshots
                                                                                              WHERE property_id = ? AND checkin_date >= date('now')
                                                                                                              ORDER BY checkin_date ASC LIMIT ?""", c, params=(property_id, days))

                            def resolve_alert(self, alert_id: int):
                                      with self.conn() as c:
                                                    c.execute("UPDATE alerts SET is_resolved=1 WHERE id=?", (alert_id,))

                                  def check_price_exists(self, property_id: int, ota: str, checkin: str) -> bool:
                                            with self.conn() as c:
                                                          r = c.execute(
                                                                            "SELECT 1 FROM price_snapshots WHERE property_id=? AND ota=? AND checkin_date=?",
                                                                            (property_id, ota, checkin)).fetchone()
                                                          return r is not None

                                        def get_historical_parity(self, days: int = 30) -> pd.DataFrame:
                                                  with self.conn() as c:
                                                                return pd.read_sql(f"""
                                                                                SELECT checkin_date, parity_status, parity_variance_pct,
                                                                                                       lowest_ota, min_price, max_price
                                                                                                                       FROM parity_snapshots
                                                                                                                                       ORDER BY scraped_at DESC LIMIT {days}""", c)
                                                    
