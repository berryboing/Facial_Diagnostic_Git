import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image, ImageGrab, ImageTk
import numpy as np
from torchvision.models import vit_b_16
import tkinter as tk
from tkinter import font as tkfont
import os
import time
import json
import qrcode 
import uuid 

# --- Cloud SDKs ---
import cloudinary
import cloudinary.uploader
import firebase_admin
from firebase_admin import credentials, firestore

# ==========================================
# 1. CLOUD INITIALIZATION
# ==========================================
cloudinary.config( 
  cloud_name = "dxmd685vr", 
  api_key = "228849167966948", 
  api_secret = "u8LBOu7lEn97TP6KNQ7bkITiugA",
  secure = True
)

try:
    cred = credentials.Certificate('firebase_key.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase Database connected successfully!")
except Exception as e:
    print(f"❌ Firebase setup failed. Check your JSON key: {e}")

# ==========================================
# 2. AI MODEL SETUP
# ==========================================
def load_model(weights_path):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Loading model on: {device}")
    
    # Reverted back to Vision Transformer to match your .pth file
    model = vit_b_16() 
    model.heads.head = nn.Sequential(
        nn.BatchNorm1d(768),
        nn.Dropout(0.5),       
        nn.Linear(768, 7)      
    )
    
    try:
        model.load_state_dict(torch.load(weights_path, map_location=device))
        print("✅ Model weights loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load model weights: {e}")
        
    model.eval()      
    model.to(device)  
    return model, device

# ==========================================
# 3. KIOSK UI FUNCTIONS
# ==========================================
def show_pairing_qr(master_root, session_id):
    window = tk.Toplevel(master_root)
    window.title("Pair Device")
    window.geometry("650x480") 
    window.configure(bg="#FFFFFF") 
    
    def set_fullscreen():
        window.attributes('-fullscreen', True)
    window.after(150, set_fullscreen)
    window.bind("<Escape>", lambda e: window.destroy())

    qr_payload = json.dumps({"session_id": session_id})

    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white")
    tk_img = ImageTk.PhotoImage(qr_img)

    tk.Label(window, text="1. Create an account on the Web App", font=("Helvetica", 14), bg="#FFFFFF", fg="#2C3E50").pack(pady=(30, 5))
    tk.Label(window, text="2. Go to 'Scan to Connect' and scan this QR", font=("Helvetica", 14), bg="#FFFFFF", fg="#2C3E50").pack(pady=5)
    
    img_label = tk.Label(window, image=tk_img, bg="#FFFFFF")
    img_label.image = tk_img 
    img_label.pack(pady=10)

    status_label = tk.Label(window, text="Waiting for device connection...", font=("Helvetica", 12, "bold", "italic"), bg="#FFFFFF", fg="#E67E22")
    status_label.pack(pady=20)

    # --- THREAD-SAFE POLLING & EMAIL CAPTURE ---
    connection_status = {"is_connected": False, "email": "unknown"}

    session_ref = db.collection('sessions').document(session_id)
    session_ref.set({
        'status': 'waiting',
        'timestamp': firestore.SERVER_TIMESTAMP
    })

    def on_snapshot(doc_snapshot, changes, read_time):
        for doc in doc_snapshot:
            if doc.exists:
                data = doc.to_dict()
                if data.get('status') == 'connected':
                    connection_status["is_connected"] = True
                    connection_status["email"] = data.get('email', 'unknown@email.com')

    doc_watch = session_ref.on_snapshot(on_snapshot)

    def check_connection():
        if connection_status["is_connected"]:
            status_label.config(text="✅ Connected successfully! Starting...", fg="#27AE60")
            window.after(1000, window.destroy)
        else:
            window.after(500, check_connection)

    check_connection()
    master_root.wait_window(window)
    doc_watch.unsubscribe()
    
    return connection_status["email"]

def show_privacy_notice(master_root):
    window = tk.Toplevel(master_root) 
    window.title("Privacy Notice")
    window.geometry("650x480") 
    window.configure(bg="#FFFFFF") 
    
    def set_fullscreen():
        window.attributes('-fullscreen', True)
        
    window.after(150, set_fullscreen)
    window.bind("<Escape>", lambda e: window.destroy())

    title_font = tkfont.Font(family="Helvetica", size=16, weight="bold")
    body_font = tkfont.Font(family="Helvetica", size=10) 
    
    tk.Label(window, text="Privacy Notice & Terms of Use", font=title_font, bg="#FFFFFF", fg="#2C3E50").pack(pady=(25, 10))
    
    privacy_text = (
        "By using this facial scanning tool, users acknowledge and agree that the system is intended "
        "solely for initial emotional assessment and support purposes and does not provide medical or "
        "psychological diagnosis.\n\n"
        "The application does not permanently store, save, or share any facial images, video captures, "
        "or biometric data obtained during the scanning process. Only the generated assessment results "
        "and related records are processed by the system.\n\n"
        "Users may choose whether to save their results locally, store them through cloud-based services, "
        "or proceed without saving any records. Access to saved records is limited only to the respective "
        "user and authorized administrators responsible for system management and data security. All "
        "information collected and processed by the system will be treated confidentially and handled in "
        "accordance with applicable data privacy and confidentiality standards."
    )
    
    text_frame = tk.Frame(window, bg="#F8F9F9", padx=20, pady=15, relief=tk.FLAT, borderwidth=1)
    text_frame.pack(fill=tk.X, padx=30, pady=5)
    
    tk.Label(text_frame, text=privacy_text, font=body_font, bg="#F8F9F9", fg="#2C3E50", wraplength=550, justify=tk.LEFT).pack()
    
    tk.Label(window, text="( Tap anywhere to agree and continue )", font=("Helvetica", 12, "bold"), bg="#FFFFFF", fg="#3498DB").pack(pady=(20, 10))

    def on_tap(event):
        window.unbind_all("<Button-1>") 
        window.destroy()

    window.bind_all("<Button-1>", on_tap)
    master_root.wait_window(window)

def process_and_upload(master_root, clean_frame, face_rgb, session_id, model, device, transform):
    window = tk.Toplevel(master_root)
    window.title("Processing...")
    window.geometry("650x480") 
    window.configure(bg="#FFFFFF") 
    
    def set_fullscreen():
        window.attributes('-fullscreen', True)
    window.after(150, set_fullscreen)
    
    tk.Label(window, text="Analyzing Facial Data...", font=("Helvetica", 16, "bold"), bg="#FFFFFF", fg="#2C3E50").pack(expand=True)
    window.update() 

    pil_img = Image.fromarray(face_rgb)
    input_tensor = transform(pil_img).unsqueeze(0).to(device)

    with torch.no_grad(): 
        output = model(input_tensor)
        probabilities = F.softmax(output, dim=1)[0] 

    scores = probabilities.cpu().numpy() * 100
    raw_dep = (scores[4] * 0.60) + (scores[6] * 0.40)  
    raw_anx = (scores[2] * 0.60) + (scores[5] * 0.40)  
    raw_str = (scores[0] * 0.50) + (scores[1] * 0.50)  

    dep_score = min(raw_dep, 100.0)
    anx_score = min(raw_anx, 100.0)
    str_score = min(raw_str, 100.0)

    # Adding artificial delay
    time.sleep(3)

    window.destroy()
    return dep_score, anx_score, str_score

def show_results_and_save(master_root, dep_score, anx_score, str_score, session_id, user_email):
    window = tk.Toplevel(master_root)
    window.title("Facial Scanning Report")
    window.geometry("650x480") 
    window.configure(bg="#FFFFFF") 
    
    def set_fullscreen():
        window.attributes('-fullscreen', True)
    window.after(150, set_fullscreen)

    title_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
    body_font = tkfont.Font(family="Helvetica", size=10)
    
    text_dark = "#2C3E50"  
    bg_gray = "#F8F9F9"    

    tk.Label(window, text="NOTICE: This is just an initial assessment using facial scanning technology and is not a clinical diagnosis.", font=tkfont.Font(family="Helvetica", size=9, slant="italic"), bg="#FFFFFF", fg="#E67E22").pack(pady=(10, 0))
    tk.Label(window, text="Initial Assessment Results", font=title_font, bg="#FFFFFF", fg=text_dark).pack(pady=(10, 5))

    slight_list, increased_list = [], []
    dep_thresh, anx_thresh, str_thresh = (36.0, 71.0), (36.0, 71.0), (36.0, 71.0) 

    if dep_thresh[0] <= dep_score < dep_thresh[1]: slight_list.append("depression")
    elif dep_score >= dep_thresh[1]: increased_list.append("depression")
    if anx_thresh[0] <= anx_score < anx_thresh[1]: slight_list.append("anxiety")
    elif anx_score >= anx_thresh[1]: increased_list.append("anxiety")
    if str_thresh[0] <= str_score < str_thresh[1]: slight_list.append("stress")
    elif str_score >= str_thresh[1]: increased_list.append("stress")

    def format_list(items):
        if not items: return ""
        if len(items) == 1: return items[0]
        if len(items) == 2: return f"{items[0]} and {items[1]}"
        return f"{items[0]}, {items[1]}, and {items[2]}"

    if increased_list:
        all_elevated = format_list(slight_list + increased_list)
        main_text = f"Based on your facial scan, the results indicate patterns consistent with what is commonly described as {all_elevated}.\n\nOur role is to provide an initial assessment only. We are not a substitute for professional medical or mental health care.\n\nWe recommend you schedule a consultation with a licensed mental health specialist (like a therapist, counselor, or doctor). This is a completely normal and positive step. A specialist can confirm your symptoms, offer a proper diagnosis, and create a personalized plan to help you feel your best."
    elif slight_list:
        slight_str = format_list(slight_list)
        main_text = f"Based on your facial scan, the results indicate mild patterns that may be associated with early or slight signs of {slight_str}. These indicators are not necessarily a cause for concern but may suggest that you are experiencing some emotional strain.\n\nOur role is to provide an initial assessment only. We are not a substitute for professional medical or mental health care.\n\nAt this stage, you may benefit from simple self-care practices such as taking breaks, getting enough sleep, and managing daily stress. While not required, you might also consider speaking with a licensed mental health professional for additional guidance."
    else:
        main_text = "Based on your facial scan, there are little to no significant patterns that suggest noticeable levels of anxiety, depression, or stress at this time. Your results appear within a typical or balanced range.\n\nOur role is to provide an initial assessment only. We are not a substitute for professional medical or mental health care.\n\nEven so, it is still important to maintain good mental well-being. Practicing healthy habits such as proper rest, regular physical activity, and staying connected with others can help you continue feeling your best."

    text_frame = tk.Frame(window, bg=bg_gray, padx=15, pady=15, relief=tk.FLAT, borderwidth=1)
    text_frame.pack(fill=tk.X, expand=False, padx=30, pady=5)
    tk.Label(text_frame, text=main_text, font=body_font, bg=bg_gray, fg=text_dark, wraplength=560, justify=tk.LEFT).pack(anchor="w")

    sync_label = tk.Label(window, text="Syncing results to Web App...", font=("Helvetica", 11, "bold"), bg="#FFFFFF", fg="#E67E22")
    sync_label.pack(pady=(15, 5))
    window.update()

    save_dir = "snapshots"
    if not os.path.exists(save_dir): os.makedirs(save_dir)
    res_path = os.path.join(save_dir, f"result_{session_id}_{int(time.time())}.jpg")
    
    try:
        window.attributes('-topmost', True)
        window.update()
        time.sleep(0.3)
        x, y, w = window.winfo_rootx(), window.winfo_rooty(), window.winfo_width()
        crop_y_bottom = text_frame.winfo_rooty() + text_frame.winfo_height() + 15 
        ImageGrab.grab(bbox=(x, y, x + w, crop_y_bottom)).save(res_path)
        window.attributes('-topmost', False)
    except Exception as e:
        print(f"Screenshot Error: {e}")
        res_path = None

    result_url = ""
    try:
        if res_path and os.path.exists(res_path):
            result_resp = cloudinary.uploader.upload(res_path, folder="thesis_results")
            result_url = result_resp['secure_url']
            
        doc_ref = db.collection('assessment_results').document()
        doc_ref.set({
            'session_id': session_id,
            'email': user_email,
            'depression': float(dep_score),
            'anxiety': float(anx_score),
            'stress': float(str_score),
            'result_url': result_url,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        sync_label.config(text="✅ Results successfully synced!", fg="#27AE60")
    except Exception as e:
        sync_label.config(text="❌ Failed to sync to cloud.", fg="#E74C3C")
        print(e)

    tk.Label(window, text="( Tap anywhere to continue )", font=("Helvetica", 11), bg="#FFFFFF", fg="#3498DB").pack(pady=10)

    dass_dep, dass_anx, dass_str = (dep_score / 100.0) * 42.0, (anx_score / 100.0) * 42.0, (str_score / 100.0) * 42.0
    hidden_frame = tk.Frame(window, bg="#EAECEE", borderwidth=1, relief=tk.SUNKEN)
    hidden_frame.place(x=0, y=480, width=650, height=60)
    tk.Label(hidden_frame, text="Backend DASS-21 Score Equivalents (Max 42)", font=tkfont.Font(family="Helvetica", size=9, weight="bold"), bg="#EAECEE", fg="#7F8C8D").pack(pady=(5, 0))
    tk.Label(hidden_frame, text=f"Depression: {dass_dep:.1f}  |  Anxiety: {dass_anx:.1f}  |  Stress: {dass_str:.1f}", font=tkfont.Font(family="Helvetica", size=10), bg="#EAECEE", fg="#2C3E50").pack()

    def on_tap(event):
        window.unbind_all("<Button-1>")
        window.destroy()

    window.bind_all("<Button-1>", on_tap)
    master_root.wait_window(window)


def show_next_steps_ui(master_root):
    window = tk.Toplevel(master_root)
    window.title("Next Steps")
    window.geometry("650x480") 
    window.configure(bg="#FFFFFF") 
    
    def set_fullscreen():
        window.attributes('-fullscreen', True)
    window.after(150, set_fullscreen)

    choice = {"action": "stop"}

    tk.Label(window, text="What would you like to do next?", font=("Helvetica", 18, "bold"), bg="#FFFFFF", fg="#2C3E50").pack(pady=(120, 40))

    def on_again():
        choice["action"] = "again"
        window.destroy()

    def on_stop():
        choice["action"] = "stop"
        window.destroy()

    btn_frame = tk.Frame(window, bg="#FFFFFF")
    btn_frame.pack()

    again_btn = tk.Button(btn_frame, text="Scan Again\n(Same Account)", font=("Helvetica", 12, "bold"), bg="#3498DB", fg="white", width=20, pady=15, command=on_again)
    again_btn.pack(side=tk.LEFT, padx=20)

    stop_btn = tk.Button(btn_frame, text="Stop Scanning\n(Disconnect)", font=("Helvetica", 12, "bold"), bg="#E74C3C", fg="white", width=20, pady=15, command=on_stop)
    stop_btn.pack(side=tk.LEFT, padx=20)

    master_root.wait_window(window)
    return choice["action"]


# ==========================================
# 4. MAIN APPLICATION LOGIC
# ==========================================
camera_tapped = False

def camera_click_event(event, x, y, flags, param):
    global camera_tapped
    if event == cv2.EVENT_LBUTTONDOWN:  
        camera_tapped = True

def draw_outlined_text(img, text, pos, scale, thickness, main_color, outline_color):
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_DUPLEX, scale, outline_color, thickness + 3, cv2.LINE_AA)
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_DUPLEX, scale, main_color, thickness, cv2.LINE_AA)

def main():
    global camera_tapped
    model_path = 'student_emotion_resnet34_best.pth' 
    model, device = load_model(model_path)

    transform = transforms.Compose([
        transforms.Resize((224, 224)), 
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]) 
    ])

    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)

    master_root = tk.Tk()
    master_root.attributes('-fullscreen', True)
    master_root.configure(bg="black")
    master_root.bind("<Escape>", lambda e: master_root.destroy())

    cap = cv2.VideoCapture(0)

    terminate_app = False 

    while not terminate_app:
        try:
            if not master_root.winfo_exists(): break
        except tk.TclError:
            break 
            
        cv2.destroyAllWindows() 
        master_root.update() 
        
        current_session_id = str(uuid.uuid4())
        current_user_email = show_pairing_qr(master_root, current_session_id)

        show_privacy_notice(master_root)

        session_active = True
        while session_active and not terminate_app:
            
            cv2.namedWindow('Thesis Camera', cv2.WINDOW_NORMAL)
            cv2.setWindowProperty('Thesis Camera', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            cv2.setMouseCallback('Thesis Camera', camera_click_event)
            camera_tapped = False
            
            face_rgb = None
            clean_frame = None
            show_warning = False
            warning_timer = 0

            while True:
                ret, frame = cap.read()
                if not ret: break

                display_frame = frame.copy()
                height, width = display_frame.shape[:2]

                tap_text = "Tap screen to Scan"
                text_size = cv2.getTextSize(tap_text, cv2.FONT_HERSHEY_DUPLEX, 1.2, 2)[0]
                text_x = (width - text_size[0]) // 2
                text_y = (height // 2) - 100
                draw_outlined_text(display_frame, tap_text, (text_x, text_y), 1.2, 2, (255, 255, 255), (0, 0, 0))

                if show_warning:
                    if time.time() - warning_timer < 2.0:
                        err_text = "NO FACE DETECTED! Try again."
                        err_size = cv2.getTextSize(err_text, cv2.FONT_HERSHEY_DUPLEX, 0.8, 2)[0]
                        err_x = (width - err_size[0]) // 2
                        err_y = height - 50  
                        draw_outlined_text(display_frame, err_text, (err_x, err_y), 0.8, 2, (0, 0, 255), (255, 255, 255))
                    else:
                        show_warning = False

                cv2.imshow('Thesis Camera', display_frame)

                key = cv2.waitKey(1) & 0xFF
                
                if key == 27 or key == ord('q'):
                    terminate_app = True
                    break 

                elif key == 32 or camera_tapped: 
                    camera_tapped = False 
                    
                    gray_cap = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces_cap = face_cascade.detectMultiScale(gray_cap, scaleFactor=1.3, minNeighbors=5)

                    if len(faces_cap) == 0:
                        show_warning = True
                        warning_timer = time.time()
                    else:
                        clean_frame = frame.copy() 
                        x, y, w, h = faces_cap[0] 
                        face_crop = clean_frame[y:y+h, x:x+w]
                        face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                        break 

            if terminate_app or not session_active:
                break 

            if face_rgb is not None:
                cv2.destroyAllWindows()
                master_root.update()

                dep, anx, str_s = process_and_upload(master_root, clean_frame, face_rgb, current_session_id, model, device, transform)
                
                show_results_and_save(master_root, dep, anx, str_s, current_session_id, current_user_email)
                
                next_action = show_next_steps_ui(master_root)
                if next_action == "stop":
                    session_active = False 

    cap.release()
    cv2.destroyAllWindows()
    try:
        master_root.destroy()
    except tk.TclError:
        pass

if __name__ == '__main__':
    main()