from app.services.rag_engine import rag_engine
from app.services.crawler import crawler

def main():
    print("1. Crawling kagri.vn...")
    crawler.crawl(max_pages=300)
    
    print("\n2. Rebuilding Vector Index (lọc tài liệu trùng DB)...")
    rag_engine.rebuild_index()
    
    print("\nDone! System is ready.")

if __name__ == "__main__":
    main()
