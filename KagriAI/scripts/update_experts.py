import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "app", "data", "db", "kagri.db")

experts_data = [
    {
        "name": "Nguyễn Văn Hiệp",
        "title": "Giám đốc quan hệ khách hàng KAGRI",
        "degree": "Kỹ sư nông nghiệp",
        "profile_url": "https://kagri.vn/chuyen-gia/",
        "bio": """Kỹ sư nông nghiệp Hiệp Nguyễn là chuyên gia trong lĩnh vực nông nghiệp và cây trồng, đồng thời là Giám đốc quan hệ khách hàng của Tập đoàn Nông nghiệp KAGRI. 
Ông tốt nghiệp Học viện Nông Nghiệp Việt Nam và đã có nhiều năm kinh nghiệm trong nghề. 
Với hơn 10 năm kinh nghiệm công tác tại các doanh nghiệp nước ngoài, ông đã cống hiến cho việc phát triển các giải pháp về dinh dưỡng tối ưu, góp phần nâng cao chất lượng và sản lượng của ngành nông nghiệp."""
    },
    {
        "name": "Lại Thế Thanh",
        "title": "Giám đốc nghiên cứu và phát triển sản phẩm KAGRI",
        "degree": "Thạc sĩ",
        "profile_url": "https://kagri.vn/chuyen-gia/",
        "bio": """Ths. Kỹ sư nông nghiệp Lại Thế Thanh
Giám đốc nghiên cứu và phát triển sản phẩm KAGRI
Học vị: Thạc sỹ
Trình độ chuyên môn: Ngành Bảo vệ thực vật
Quá trình công tác:
- 6 năm công tác tại Học viện Nông nghiệp Việt Nam trong lĩnh vực nhân lực và tham gia một số dự án của FAO, Cục Kinh tế hợp tác và PTNT (Bộ NN& PTNT), Văn phòng Quốc gia giảm nghèo bền vững liên quan tới phát triển nông nghiệp, sinh kế cho người dân.
- 3 năm tham gia lĩnh vực vật tư nông nghiệp, tham gia hoạt động khảo sát vùng trồng nguyên liệu miền Bắc của PepsiCo, dự án giảm phát thải khí nhà kính với Công ty CarbonFarm (Pháp)."""
    }
]

def update_experts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for expert in experts_data:
        # Check if expert exists by name
        cursor.execute("SELECT id FROM experts WHERE name = ?", (expert["name"],))
        row = cursor.fetchone()
        
        if row:
            print(f"Updating expert {expert['name']}...")
            cursor.execute("""
                UPDATE experts
                SET title = ?, degree = ?, profile_url = ?, bio = ?
                WHERE id = ?
            """, (expert["title"], expert["degree"], expert["profile_url"], expert["bio"], row[0]))
        else:
            print(f"Inserting expert {expert['name']}...")
            cursor.execute("""
                INSERT INTO experts (name, title, degree, profile_url, bio)
                VALUES (?, ?, ?, ?, ?)
            """, (expert["name"], expert["title"], expert["degree"], expert["profile_url"], expert["bio"]))
            
    conn.commit()
    conn.close()
    print("Experts updated successfully.")

if __name__ == "__main__":
    update_experts()
