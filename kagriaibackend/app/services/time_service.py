import datetime
import pytz
from lunarcalendar import Converter, Solar, Lunar

class TimeService:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Ho_Chi_Minh')
        self.weekdays = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"]

    def get_current_time_info(self) -> str:
        # 1. Get current time in Vietnam
        now = datetime.datetime.now(self.tz)
        
        # 2. Format time: HH:MM
        time_str = now.strftime("%H:%M")
        
        # 3. Day of week
        # Python weekday: 0=Monday, 6=Sunday. 
        # My array: 0=CN, 1=T2, ..., 6=T7
        # Conversion: 
        #   weekday() -> 0 (Mon) -> Index 1
        #   weekday() -> 6 (Sun) -> Index 0
        wd = now.weekday()
        if wd == 6:
            wd_idx = 0
        else:
            wd_idx = wd + 1
        day_of_week = self.weekdays[wd_idx]
        
        # 4. Gregorian Date
        day = now.day
        month = now.month
        year = now.year
        gregorian_date = f"ngày {day} tháng {month} năm {year}"
        
        # 5. Lunar Date
        solar = Solar(year, month, day)
        lunar = Converter.Solar2Lunar(solar)
        lunar_day = lunar.day
        lunar_month = lunar.month
        lunar_year = lunar.year
        lunar_date_str = f"ngày {lunar_day} tháng {lunar_month} năm {lunar_year} (Âm lịch)"
        
        # 6. Season
        season = self._get_season(month)
        
        # 7. Construct response
        response = (
            f"Dạ, bây giờ là **{time_str}**, **{day_of_week}**.\n"
            f"- **Dương lịch**: {gregorian_date}.\n"
            f"- **Âm lịch**: {lunar_date_str}.\n"
            f"- **Thông tin mùa**: {season}."
        )
        return response

    def convert_lunar_solar(self, date_str: str, is_lunar: bool) -> str:
        try:
            import re
            import datetime as dt
            cleaned = date_str.strip().replace(" ", "/").replace("-", "/").replace(".", "/")
            # Accept formats: dd/mm/yyyy, d/m/yyyy, yyyy/mm/dd
            nums = re.findall(r"\d{1,4}", cleaned)
            if len(nums) < 3:
                return "Dạ, em không thể chuyển đổi ngày tháng. Vui lòng nhập đúng định dạng dd/mm/yyyy."
            a, b, c = nums[0], nums[1], nums[2]
            if len(a) == 4:  # yyyy/mm/dd
                year = int(a)
                month = int(b)
                day = int(c)
            else:  # dd/mm/yyyy
                day = int(a)
                month = int(b)
                year = int(c)
            if year < 100:
                year = 2000 + year
            if is_lunar:
                try:
                    lunar = Lunar(year, month, day)
                    solar = Converter.Lunar2Solar(lunar)
                    # verify round-trip
                    lv = Converter.Solar2Lunar(Solar(solar.year, solar.month, solar.day))
                    if lv.day == day and lv.month == month:
                        return f"ngày {solar.day} tháng {solar.month} năm {solar.year} (Dương lịch)"
                except Exception:
                    pass
                # fallback: search nearby solar dates to match lunar day/month
                start = dt.date(year - 1, 12, 1)
                for i in range(180):
                    d = start + dt.timedelta(days=i)
                    lv = Converter.Solar2Lunar(Solar(d.year, d.month, d.day))
                    if lv.day == day and lv.month == month:
                        return f"ngày {d.day} tháng {d.month} năm {d.year} (Dương lịch)"
                return "Dạ, em chưa chuyển được ngày âm sang dương. Anh/chị vui lòng nhập lại giúp em ạ."
            else:
                solar = Solar(year, month, day)
                lunar = Converter.Solar2Lunar(solar)
                return f"ngày {lunar.day} tháng {lunar.month} năm {lunar.year} (Âm lịch)"
        except Exception:
            return "Dạ, em không thể chuyển đổi ngày tháng. Vui lòng nhập đúng định dạng dd/mm/yyyy."

    def _get_season(self, month: int) -> str:
        if month in [1, 2, 3]:
            return "Mùa Xuân - Thời tiết ấm áp, cây cối đâm chồi nảy lộc"
        elif month in [4, 5, 6]:
            return "Mùa Hè - Thời tiết nắng nóng, mưa rào"
        elif month in [7, 8, 9]:
            return "Mùa Thu - Thời tiết mát mẻ, hanh khô"
        elif month in [10, 11, 12]:
            return "Mùa Đông - Thời tiết lạnh giá"
        return ""

time_service = TimeService()
