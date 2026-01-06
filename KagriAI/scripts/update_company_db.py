import sqlite3
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "app", "data", "db", "kagri.db")

def get_db_path():
    return DB_PATH

def update_db():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    row = cursor.execute("SELECT id FROM company_info LIMIT 1").fetchone()
    name = "Công ty Cổ phần Tập đoàn Nông nghiệp KAGRI"
    address = "Thửa đất số T210, Khu TĐC dự án đường Dốc Hội - ĐHNN1, Thị trấn Trâu Quỳ, Huyện Gia Lâm, Thành phố Hà Nội, Việt Nam"
    slogan = "Chuyên gia của nhà nông"
    hotline = "0985 562 582"
    email = "contact@kagri.vn"
    website = "https://kagri.vn/"
    introduction = (
        "Công ty Cổ phần Tập đoàn Nông nghiệp KAGRI là doanh nghiệp tiên phong trong lĩnh vực nông nghiệp công nghệ cao, "
        "chuyên cung cấp các giải pháp tiên tiến về phân bón và chế phẩm sinh học. Chúng tôi tập trung nghiên cứu và phát triển các sản phẩm chất lượng cao, "
        "được ứng dụng khoa học công nghệ hiện đại, nhằm nâng cao năng suất và chất lượng cây trồng tại Việt Nam. "
        "Với sứ mệnh mang đến những giải pháp trồng trọt cho bà con nông dân, KAGRI không ngừng cải tiến để mang đến các dòng sản phẩm phù hợp với mọi loại cây trồng, "
        "điều kiện thổ nhưỡng và khí hậu Việt Nam. Sản phẩm của chúng tôi đảm bảo an toàn, không chứa hóa chất độc hại, thân thiện với môi trường, góp phần xây dựng một nền nông nghiệp bền vững. "
        "Nhà máy sản xuất của KAGRI đạt tiêu chuẩn GMP & ISO, đảm bảo quy trình kiểm soát chất lượng nghiêm ngặt. "
        "Bên cạnh đó, chúng tôi cũng là những kỹ sư, chuyên gia trong lĩnh vực nông nghiệp với hơn 20 năm kinh nghiệm luôn đồng hành để tư vấn, hướng dẫn giúp bà con nông dân đạt được hiệu quả canh tác, trồng trọt cao nhất! "
        "KAGRI tin rằng, việc ứng dụng khoa học công nghệ hiện đại của Việt Nam sẽ giúp người nông dân giảm thiểu các rủi ro trong quá trình trồng trọt, "
        "nâng cao năng suất, thu nhập và mang lại những giá trị trọn đời cho người nông dân. "
        "Các sản phẩm của KAGRI được nghiên cứu phát triển bởi đội ngũ các nhà khoa học đầu ngành cùng với "
        "các chuyên gia xuất sắc đến từ Học viện Nông nghiệp Việt Nam và Bộ Nông nghiệp & PTNT"
    )
    vision = "Mở rộng sang các thị trường tiềm năng tại Đông Nam Á, Châu Âu và Châu Mỹ, mang giải pháp nông nghiệp bền vững đến với nhiều nhà nông trên khắp thế giới."
    mission = "Áp dụng các tiến bộ trong nghiên cứu khoa học và công nghệ của Việt Nam vào sản phẩm, nhằm mang lại hiệu quả tối ưu cho người nông dân."
    core_values = "Đội ngũ là các bác sĩ, chuyên gia của chúng tôi sát cánh bên cạnh trong suốt cả quá trình trồng trọt."
    factories = (
        "Hệ thống nhà máy của KAGRI đạt chứng nhận đủ điều kiện sản xuất phân bón như ISO và VICAS 087 – QSM, "
        "được đầu tư kĩ lưỡng từ các trang thiết bị và dây chuyền sản xuất tiên tiến nhất, đảm bảo cung cấp các sản phẩm đạt chuẩn đầu ra"
    )
    license_tax = "MST:109210397/ GPKD số 109210397 cấp ngày 05/06/2020 tại Sở KHĐT Thành phố Hà Nội"

    if row:
        cursor.execute("""
            UPDATE company_info
            SET name = ?, address = ?, slogan = ?, hotline = ?, email = ?, website = ?, introduction = ?, vision = ?, mission = ?, core_values = ?, factories = ?, license_tax = ?
            WHERE id = ?
        """, (name, address, slogan, hotline, email, website, introduction, vision, mission, core_values, factories, license_tax, row[0]))
    else:
        cursor.execute("""
            INSERT INTO company_info (name, address, slogan, hotline, email, website, introduction, vision, mission, core_values, factories, license_tax)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, address, slogan, hotline, email, website, introduction, vision, mission, core_values, factories, license_tax))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_db()
