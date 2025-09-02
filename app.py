# app.py
import gradio as gr
import joblib
import pandas as pd
import re

# --- TẢI MÔ HÌNH ---

try:
    svm_pipeline = joblib.load("models/svm_pipeline.pkl")
except FileNotFoundError:
    # Cung cấp thông báo lỗi thân thiện nếu không tìm thấy file
    print("LỖI: Không tìm thấy file 'models/svm_pipeline_full.pkl'.")
    print("Hãy chắc chắn rằng bạn đã tải file model lên đúng thư mục 'models'.")
    svm_pipeline = None # Đặt là None để ứng dụng không bị crash hoàn toàn

# --- CÁC HÀM HỖ TRỢ ---
def has_url(text):
    # Regex để tìm URL trong văn bản
    pattern = (
        r'\b(?:http[s]?://)?'
        r'(?:(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}|(?:\d{1,3}\.){3}\d{1,3})'
        r'(?:\:\d{1,5})?(?:/[^\s]*)?\b'
    )
    return int(bool(re.search(pattern, text, re.IGNORECASE)))

# --- HÀM DỰ ĐOÁN CHÍNH ---
def predict_text(msg):
    # Nếu không tải được model, trả về thông báo lỗi
    if svm_pipeline is None:
        return "Lỗi: Không thể tải mô hình phân loại.", "Vui lòng kiểm tra lại file model."

    # Tạo một DataFrame từ input, vì pipeline của bạn có vẻ cần cấu trúc này
    features = pd.DataFrame([{
        'clean_texts': msg,
        'has_money': int(bool(re.search(r'\b\d+(?:[.,]\d+)?\s*(?:k|nghìn|triệu|tỷ|đ|vnd|vnđ|\$|usd|€|eur)\b', msg, re.IGNORECASE))),
        'has_url': has_url(msg),
        'has_phone': int(bool(re.search(r'\b(\+84|0)(\d[\s.]?){8,10}\b', msg)))
    }])

    try:
        # Dự đoán nhãn và xác suất
        pred_label = svm_pipeline.predict(features)[0]
        prob = svm_pipeline.predict_proba(features)[0]
    except Exception as e:
        return f"Lỗi khi dự đoán: {e}", ""

    # Diễn giải kết quả
    prob_scam = prob[1] # Xác suất là lừa đảo (nhãn 1)
    
    if pred_label == 1 and prob[1] > 0.8:
        label_str = "⚠️ Khả năng cao là lừa đảo"
    else:
        label_str = "✅ Chưa đủ dữ kiện để xác nhận lừa đảo"
        
    prob_str = f"Khả năng lừa đảo: {prob_scam*100:.2f}%"
    
    return label_str, prob_str

# --- GIAO DIỆN GRADIO ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # 🚨 Phân loại tin nhắn lừa đảo bằng SVM
        Nhập một tin nhắn vào ô bên dưới để kiểm tra xem nó có dấu hiệu lừa đảo hay không.
        """
    )

    with gr.Row():
        with gr.Column():
            msg_input = gr.Textbox(lines=5, label="Nội dung tin nhắn", placeholder="Ví dụ: Chúc mừng bạn đã trúng thưởng 1 chiếc iPhone 15 Pro Max, bấm vào link abc.xyz để nhận giải...")
            btn = gr.Button("Kiểm tra", variant="primary")
        with gr.Column():
            label_output = gr.Textbox(label="Kết quả phân loại", interactive=False)
            prob_output = gr.Textbox(label="Độ tin cậy", interactive=False)

    btn.click(
        fn=predict_text, 
        inputs=msg_input, 
        outputs=[label_output, prob_output]
    )

# --- KHỞI CHẠY ỨNG DỤNG ---
if __name__ == "__main__":
    demo.launch(share=True)