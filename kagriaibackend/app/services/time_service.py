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
        return self.get_date_info(date_str, is_lunar)

    def get_date_info(self, date_str: str, is_lunar: bool) -> str:
        try:
            import re
            import datetime as dt
            cleaned = date_str.strip().replace(" ", "/").replace("-", "/").replace(".", "/")
            nums = re.findall(r"\d{1,4}", cleaned)
            if len(nums) < 3:
                return "Dạ, em không thể chuyển đổi ngày tháng. Vui lòng nhập đúng định dạng dd/mm/yyyy."
            a, b, c = nums[0], nums[1], nums[2]
            if len(a) == 4:
                year = int(a); month = int(b); day = int(c)
            else:
                day = int(a); month = int(b); year = int(c)
            if year < 100:
                year = 2000 + year
            solar_date = None
            lunar_date = None
            if is_lunar:
                try:
                    ln = Lunar(year, month, day)
                    sl = Converter.Lunar2Solar(ln)
                    solar_date = dt.date(sl.year, sl.month, sl.day)
                    lunar_date = Converter.Solar2Lunar(Solar(sl.year, sl.month, sl.day))
                except Exception:
                    start = dt.date(max(1, year - 1), 1 if month == 1 else 12, 1)
                    for i in range(365):
                        d = start + dt.timedelta(days=i)
                        lv = Converter.Solar2Lunar(Solar(d.year, d.month, d.day))
                        if lv.day == day and lv.month == month:
                            solar_date = d
                            lunar_date = lv
                            break
                    if solar_date is None:
                        return "Dạ, em chưa chuyển được ngày âm sang dương. Anh/chị vui lòng nhập lại giúp em ạ."
            else:
                sl = Solar(year, month, day)
                solar_date = dt.date(year, month, day)
                lunar_date = Converter.Solar2Lunar(sl)
            wd = solar_date.weekday()
            wd_idx = 0 if wd == 6 else wd + 1
            day_of_week = self.weekdays[wd_idx]
            season = self._get_season(solar_date.month)
            gregorian = f"ngày {solar_date.day} tháng {solar_date.month} năm {solar_date.year}"
            lunar_str = f"ngày {lunar_date.day} tháng {lunar_date.month} năm {lunar_date.year} (Âm lịch)"
            return (
                f"**{day_of_week}**.\n"
                f"- **Dương lịch**: {gregorian}.\n"
                f"- **Âm lịch**: {lunar_str}.\n"
                f"- **Mùa**: {season}."
            )
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
