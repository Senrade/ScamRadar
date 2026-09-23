# ==============================================================================
# SECTION 1: SETUP
# ==============================================================================

import gradio as gr
import joblib
import pandas as pd
import re
import os
import traceback
from urllib.parse import urlparse

# Tải mô hình SVM đã được huấn luyện
try:
    svm_pipeline = joblib.load("models/svm_pipeline.pkl")
    print("SUCCESS: Đã tải mô hình SVM thành công.")
except FileNotFoundError:
    print("LỖI: Không tìm thấy file 'models/svm_pipeline.pkl'.")
    svm_pipeline = None

# Khai báo các danh sách từ khóa và tên miền
URL_SHORTENER_DOMAINS = [
    'bit.ly', 't.co', 'tinyurl.com', 'is.gd', 'soo.gd', 's.id', 'lnkd.in', 
    'db.tt', 'qr.ae', 'ow.ly', 'buff.ly', 'adf.ly', 'tr.im'
]
AUTHORITY_KEYWORDS = [
    'chính phủ', 'thủ tướng', 'nhà nước', 'bộ công an', 'bộ quốc phòng', 'tổng đài quốc gia',
    'bộ y tế', 'bộ tài chính', 'vtv', 'vneid', 'an sinh xã hội', 'nghị quyết'
]

TRUSTED_ENTITIES = {
    'vietnamobile': 'vietnamobile.com.vn', 'viettel': 'viettel.vn', 
    'viettelpay': 'viettel.vn', 'viettel money': 'viettel.vn', 
    'mobifone': 'mobifone.vn', 'vinaphone': 'vinaphone.com.vn',
    'bidv': 'bidv.com.vn', 'smartbanking': 'bidv.com.vn', 'momo': 'momo.vn',
    'techcombank': 'techcombank.com', 'vietinbank': 'vietinbank.vn',
    'vietcombank': 'vietcombank.com.vn', 'agribank': 'agribank.com.vn',
    'mb bank': 'mbbank.com.vn', 'shopee': 'shopee.vn', 'lazada': 'lazada.vn',
    'tiki': 'tiki.vn'
}

TRUSTED_PHONE_NUMBERS = ['111', '113', '114', '115']

# ==============================================================================
# SECTION 2: VIẾT HÀM XỬ LÝ INPUT
# ==============================================================================

def get_domain_from_url(url):
    """Trích xuất tên miền chính từ một URL đầy đủ."""
    try:
        if '://' not in url:
            url = 'http://' + url
        parsed_uri = urlparse(url)
        domain = "{uri.netloc}".format(uri=parsed_uri).replace('www.', '')
        parts = domain.split('.')
        if len(parts) > 2 and parts[-2] in ['co', 'com', 'gov', 'org']:
            return '.'.join(parts[-3:])
        return '.'.join(parts[-2:])
    except:
        return None

def extract_features_from_text(text):
    """Trích xuất tất cả các đặc trưng cơ bản từ văn bản đầu vào."""
    lower_text = text.lower()
    url_pattern = r'(?:(?:https?://|www\.)[a-zA-Z0-9./\-_?=&%]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/\S*)?)'
    return {
        'clean_texts': text,
        'has_money': int(bool(re.search(r'\b\d+(?:[.,]\d+)?\s*(?:k|nghìn|triệu|tỷ|đ|vnd|vnđ|\$|usd|€|eur)\b', lower_text))),
        'has_url': int(bool(re.search(url_pattern, lower_text))),
        'has_phone': int(bool(re.search(r'\b(\+84|0)(\d[\s.]?){8,10}\b', lower_text)))
    }

def analyze_special_cases(text, features):
    """Phân tích các trường hợp đặc biệt, trả về một dictionary chứa thông tin về trường hợp đó."""
    lower_text = text.lower()
    url_pattern = r'(?:(?:https?://|www\.)[a-zA-Z0-9./\-_?=&%]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/\S*)?)'
    urls = re.findall(url_pattern, lower_text)
    
    has_shortener = any(get_domain_from_url(url) in URL_SHORTENER_DOMAINS for url in urls)
    
    for keyword, trusted_domain in TRUSTED_ENTITIES.items():
        if keyword in lower_text:
            if not urls: continue
            is_domain_trusted = any(get_domain_from_url(url) == trusted_domain for url in urls)
            if is_domain_trusted: return {'case': 'TRUSTED_PROMO', 'has_shortener': has_shortener}
            else: return {'case': 'BRAND_IMPERSONATION', 'has_shortener': has_shortener}

    is_authority = any(keyword in lower_text for keyword in AUTHORITY_KEYWORDS)

    if is_authority and features['has_phone'] and not features ['has_url']:
        phone_numbers_found = re.findall(r'\b\d{3,10}\b', lower_text)
        # Nếu tất cả các số điện thoại được tìm thấy đều nằm trong danh sách an toàn
        if phone_numbers_found and all(phone in TRUSTED_PHONE_NUMBERS for phone in phone_numbers_found):
            return {'case': 'SAFE_ANNOUNCEMENT', 'has_shortener': has_shortener}

    risky_action = features['has_url'] or features['has_phone']
    if is_authority:
        return {'case': 'AUTHORITY_IMPERSONATION' if risky_action else 'SAFE_ANNOUNCEMENT', 'has_shortener': has_shortener}

    return {'case': 'NORMAL', 'has_shortener': has_shortener}

def generate_explanation(features, label, case_info):
    """Tạo ra lời giải thích phù hợp với từng trường hợp."""
    case, has_shortener = case_info['case'], case_info['has_shortener']
    explanations = {
        'BRAND_IMPERSONATION': "Cảnh báo: Tin nhắn này có dấu hiệu mạo danh một thương hiệu/nhà mạng uy tín. Nó sử dụng tên thương hiệu để tạo lòng tin nhưng lại dẫn người dùng đến một trang web giả mạo.",
        'AUTHORITY_IMPERSONATION': "Cảnh báo: Tin nhắn này có dấu hiệu mạo danh một tổ chức uy tín. Nó sử dụng các thuật ngữ đáng tin cậy nhưng lại yêu cầu bạn thực hiện hành động rủi ro (bấm link lạ, gọi số lạ).",
        'SAFE_ANNOUNCEMENT': "Ghi chú: Tin nhắn chứa từ khóa từ cơ quan/tổ chức uy tín và không yêu cầu thực hiện hành động rủi ro. Hệ thống ghi nhận đây có thể là một thông báo chính thức.",
        'TRUSTED_PROMO': "Ghi chú: Mặc dù tin nhắn có các đặc điểm của tin quảng cáo, hệ thống xác định đây là một chương trình hợp lệ từ một nguồn uy tín."
    }
    if case in explanations: return explanations[case]
    if "✅" in label: return "Tin nhắn có vẻ an toàn, không chứa các dấu hiệu lừa đảo phổ biến."
    if has_shortener and "🤔" in label: return "Lưu ý: Tin nhắn này chứa một đường link rút gọn (ví dụ: bit.ly, t.co...). Đây là một kỹ thuật thường được sử dụng để che giấu trang web đích, người dùng cần hết sức cẩn thận."
    
    detected = [name for name, present in {'tiền bạc': features['has_money'], 'đường link': features['has_url'], 'số điện thoại': features['has_phone']}.items() if present]
    base = "Lưu ý: Tin nhắn này có dấu hiệu đáng ngờ vì nó" if "🤔" in label else "Cảnh báo: Tin nhắn này"
    if not detected: return f"{base} chứa các từ ngữ và cấu trúc câu thường thấy trong các tin nhắn lừa đảo."
    return f"{base} đề cập đến {', '.join(detected)}."

# ==============================================================================
# SECTION 3: HÀM DỰ ĐOÁN
# ==============================================================================

def predict_text(message):
    try:
        if svm_pipeline is None:
            raise ValueError("Mô hình SVM chưa được tải.")
        if not message or not message.strip():
            return "", "", ""

        features = extract_features_from_text(message)
        case_info = analyze_special_cases(message, features)
        case = case_info['case']

        df = pd.DataFrame([features])
        prob_scam = svm_pipeline.predict_proba(df)[0][1]
        
        final_prob = prob_scam
        if case in ['BRAND_IMPERSONATION', 'AUTHORITY_IMPERSONATION']: final_prob = 0.95 + (prob_scam * 0.049)
        elif case in ['SAFE_ANNOUNCEMENT', 'TRUSTED_PROMO']: final_prob = prob_scam * 0.1
        elif case_info['has_shortener'] and final_prob < 0.5: final_prob = 0.5 + (prob_scam * 0.1)

        if final_prob > 0.85: label = "⚠️ Khả năng cao là lừa đảo"
        elif final_prob > 0.6: label = "🤔 Có dấu hiệu đáng ngờ"
        else: label = "✅ Chưa đủ dữ kiện để xác nhận lừa đảo"
        
        prob_details = f"Khả năng lừa đảo: {final_prob*100:.2f}%"
        explanation = generate_explanation(features, label, case_info)
        
        return label, prob_details, explanation

    except Exception as e:
        error_traceback = traceback.format_exc()
        print(error_traceback) # In lỗi ra terminal để debug
        return "Lỗi Hệ Thống", "Đã có lỗi xảy ra", f"Chi tiết lỗi: {e}"

def clear_all():
    """Hàm để xóa toàn bộ nội dung trong các ô input và output."""
    return "", "", "", ""

# ==============================================================================
# SECTION 4: GIAO DIỆN NGƯỜI DÙNG
# ==============================================================================

# UPDATE: Giao diện được đơn giản hóa để tải nhanh và ổn định hơn

with gr.Blocks(theme='soft') as demo:
    gr.Markdown(
        """
        # 🚨 ScamRadar: Phân Loại Tin Nhắn Lừa Đảo
        Dán nội dung tin nhắn đáng ngờ vào ô bên dưới và nhấn "Kiểm tra".
        """
    )
    
    with gr.Row():
        with gr.Column(scale=2):
            msg_input = gr.Textbox(
                lines=8, 
                label="Nội dung tin nhắn", 
                placeholder="Ví dụ: Chuc mung quy khach da nhan duoc qua..."
            )
            with gr.Row():
                clear_btn = gr.Button("Xóa")
                check_btn = gr.Button("Kiểm tra", variant="primary")
            
        with gr.Column(scale=3):
            label_output = gr.Textbox(label="Kết quả phân loại", interactive=False)
            prob_output = gr.Textbox(label="Độ tin cậy", interactive=False)
            explain_output = gr.Textbox(label="Giải thích", interactive=False, lines=4)
            
    gr.Examples(
        examples=[
            ["Chuc mung quy khach da nhan duoc 1 luot mo tu chuong trinh SAC MAU HOA BINH RINH QUA QUOC KHANH . Vui long truy cap website https://quockhanh.vietnamobile.com.vn de nhan qua."],
            ["Chính phủ vừa ban hành Nghị quyết số 263/NQ-CP về việc tặng quà nhân dân nhân dịp kỷ niệm 80 năm Cách mạng tháng Tám và Quốc khánh 2.9."],
            ["Con bạn đã bị tai nạn trên đường Trần Duy Hưng. Hãy chuyển gấp cho tôi 5000000 VND để cứu con của bạn."],
            ["Chính phủ đã tặng cho bạn 100.000 đồng nhân dịp 2/9. Hãy đăng kí nhận qua đường link bit.ly/nhanqua29"],
            ["Tai khoan SmartBanking cua ban da bi khoa. Vui long truy cap www.bidv-vn.xyz de mo khoa ngay."],
            ["Toàn dân tích cực tham gia phòng chống mua bán người. Khi phát hiện dấu hiệu liên quan đến mua bán người xin hãy báo ngay cho cơ quan Công an nơi gần nhất hoặc Tổng đài quốc gia 111."]
        ],
        inputs=msg_input,
        label="Hoặc chọn một ví dụ có sẵn:"
    )
    
    # --- Event Handling ---
    check_btn.click(
        fn=predict_text, 
        inputs=msg_input, 
        outputs=[label_output, prob_output, explain_output]
    )
    clear_btn.click(
        fn=clear_all, 
        inputs=[], 
        outputs=[msg_input, label_output, prob_output, explain_output]
    )

# ==============================================================================
# SECTION 5: KHỐI THỰC THI CHÍNH
# ==============================================================================

if __name__ == "__main__":
    demo.launch(share=True)
