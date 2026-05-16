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

# --- Cloud SDKs ---
import cloudinary
import cloudinary.uploader

# ==========================================
# 1. CLOUD INITIALIZATION
# ==========================================
cloudinary.config( 
  cloud_name = "dxmd685vr", 
  api_key = "228849167966948", 
  api_secret = "u8LBOu7lEn97TP6KNQ7bkITiugA",
  secure = True
)

# ==========================================
# 2. AI MODEL SETUP
# ==========================================
def load_model(weights_path):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Loading model on: {device}")
    
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
# 3. UPLOAD HELPER FUNCTION
# ==========================================
def upload_to_cloudinary(result_path):
    urls = {"result": None}
    try:
        if os.path.exists(result_path):
            print("Uploading Result to Cloudinary...")
            result_resp = cloudinary.uploader.upload(result_path, folder="thesis_results")
            urls["result"] = result_resp['secure_url']
    except Exception as e:
        print(f"Cloudinary Upload Error: {e}")
    
    return urls

# ==========================================
# 4. USER INTERFACE (TKINTER) - RPi Optimized
# ==========================================
def show_privacy_notice():
    root = tk.Tk()
    root.title("Privacy Notice")
    root.geometry("650x480")
    root.resizable(False, False)
    root.configure(bg="#FFFFFF")

    title_font = tkfont.Font(family="Helvetica", size=16, weight="bold")
    body_font = tkfont.Font(family="Helvetica", size=10) # Slightly smaller to fit the new text perfectly
    
    tk.Label(root, text="Privacy Notice & Terms of Use", font=title_font, bg="#FFFFFF", fg="#2C3E50").pack(pady=(25, 10))
    
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
    
    text_frame = tk.Frame(root, bg="#F8F9F9", padx=20, pady=15, relief=tk.FLAT, borderwidth=1)
    text_frame.pack(fill=tk.X, padx=30, pady=5)
    
    tk.Label(text_frame, text=privacy_text, font=body_font, bg="#F8F9F9", fg="#2C3E50", wraplength=550, justify=tk.LEFT).pack()
    
    tk.Label(root, text="( Tap anywhere to agree and continue )", font=("Helvetica", 12, "bold"), bg="#FFFFFF", fg="#3498DB").pack(pady=(20, 10))

    def on_tap(event):
        root.unbind_all("<Button-1>") 
        root.destroy()

    root.bind_all("<Button-1>", on_tap)
    
    root.attributes('-topmost', True)
    root.update()
    root.attributes('-topmost', False)
    
    root.mainloop()

def show_results_ui(dep_score, anx_score, str_score, captured_frame):
    root = tk.Tk()
    root.title("Facial Scanning Report")
    root.geometry("650x480") 
    root.resizable(False, False) 
    root.configure(bg="#FFFFFF") 

    user_choice = {"action": "discard", "result_path": None}

    title_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
    body_font = tkfont.Font(family="Helvetica", size=10)
    btn_font = tkfont.Font(family="Helvetica", size=9, weight="bold") # Shrunk slightly to fit 3 buttons
    
    text_dark = "#2C3E50"  
    bg_gray = "#F8F9F9"    

    notice_statement = "NOTICE: This is just an initial assessment using facial scanning technology and is not a clinical diagnosis."
    tk.Label(root, text=notice_statement, font=tkfont.Font(family="Helvetica", size=9, slant="italic"), bg="#FFFFFF", fg="#E67E22").pack(pady=(10, 0))
    tk.Label(root, text="Initial Assessment Results", font=title_font, bg="#FFFFFF", fg=text_dark).pack(pady=(10, 5))

    # --- DYNAMIC TEXT LOGIC (SEPARATE THRESHOLDS) ---
    slight_list, increased_list = [], []

    dep_thresh = (36.0, 71.0) 
    anx_thresh = (36.0, 71.0) 
    str_thresh = (36.0, 71.0) 

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
        main_text = f"Based on your facial scan, the results indicate patterns consistent with what is commonly described as {all_elevated}.\n\nOur role is to provide an initial assessment only. We are not a substitute for professional medical or mental health care.\n\nWe recommend you schedule a consultation with a licensed mental health specialist (like a therapist, counselor, or doctor). This is a completely normal and positive step. A specialist can confirm your symptoms, offer a proper diagnosis, and create a personalized plan to help you feel your best.\n\nRemember: Symptoms are manageable, and seeking professional help is the most effective way to start feeling better."
    elif slight_list:
        slight_str = format_list(slight_list)
        main_text = f"Based on your facial scan, the results indicate mild patterns that may be associated with early or slight signs of {slight_str}. These indicators are not necessarily a cause for concern but may suggest that you are experiencing some emotional strain.\n\nOur role is to provide an initial assessment only. We are not a substitute for professional medical or mental health care.\n\nAt this stage, you may benefit from simple self-care practices such as taking breaks, getting enough sleep, and managing daily stress. While not required, you might also consider speaking with a licensed mental health professional for additional guidance, especially if these feelings persist or become more noticeable over time.\n\nRemember: Early awareness is valuable, and taking small steps to care for your mental health can make a meaningful difference."
    else:
        main_text = "Based on your facial scan, there are little to no significant patterns that suggest noticeable levels of anxiety, depression, or stress at this time. Your results appear within a typical or balanced range.\n\nOur role is to provide an initial assessment only. We are not a substitute for professional medical or mental health care.\n\nEven so, it is still important to maintain good mental well-being. Practicing healthy habits such as proper rest, regular physical activity, and staying connected with others can help you continue feeling your best. If you ever notice changes in how you feel, seeking guidance from a licensed mental health professional is always a helpful and proactive step.\n\nRemember: Maintaining mental wellness is an ongoing process, and staying mindful of your well-being is a positive step forward."

    text_frame = tk.Frame(root, bg=bg_gray, padx=15, pady=15, relief=tk.FLAT, borderwidth=1)
    text_frame.pack(fill=tk.X, expand=False, padx=30, pady=5)
    tk.Label(text_frame, text=main_text, font=body_font, bg=bg_gray, fg=text_dark, wraplength=560, justify=tk.LEFT).pack(anchor="w")

    root.update()

    # --- ACTION HANDLERS ---
    def capture_screenshot():
        save_dir = "snapshots"
        if not os.path.exists(save_dir): os.makedirs(save_dir)
        timestamp = int(time.time())
        res_path = os.path.join(save_dir, f"result_{timestamp}.jpg")
        
        try:
            root.attributes('-topmost', True)
            root.update()
            time.sleep(0.3)
            x, y, w = root.winfo_rootx(), root.winfo_rooty(), root.winfo_width()
            crop_y_bottom = text_frame.winfo_rooty() + text_frame.winfo_height() + 15 
            ImageGrab.grab(bbox=(x, y, x + w, crop_y_bottom)).save(res_path)
            root.attributes('-topmost', False)
            return res_path
        except Exception as e:
            print(f"Screenshot Error: {e}")
            return None

    def on_discard():
        user_choice["action"] = "discard"
        root.destroy()

    def on_local():
        user_choice["action"] = "local"
        user_choice["result_path"] = capture_screenshot()
        root.destroy()

    def on_qr():
        user_choice["action"] = "qr"
        user_choice["result_path"] = capture_screenshot()
        root.destroy()

    # --- 3 TOUCH BUTTONS ---
    btn_frame = tk.Frame(root, bg="#FFFFFF")
    btn_frame.pack(fill=tk.X, padx=15, pady=10)

    discard_btn = tk.Button(btn_frame, text="Discard\n(Do Not Save)", font=btn_font, bg="#E74C3C", fg="white", width=15, pady=8, command=on_discard)
    discard_btn.pack(side=tk.LEFT, expand=True, padx=5)

    local_btn = tk.Button(btn_frame, text="Save Locally\n(Device Only)", font=btn_font, bg="#7F8C8D", fg="white", width=15, pady=8, command=on_local)
    local_btn.pack(side=tk.LEFT, expand=True, padx=5)

    qr_btn = tk.Button(btn_frame, text="Save to Web App\n(Generate QR)", font=btn_font, bg="#27AE60", fg="white", width=15, pady=8, command=on_qr)
    qr_btn.pack(side=tk.LEFT, expand=True, padx=5)

    root.mainloop()
    
    return user_choice["action"], user_choice["result_path"]

    # ==========================================
    # MODIFICATION: THE HIDDEN SCORES FRAME
    # ==========================================
    # Converts your 0-100% predictions to the DASS Max 42 format for local viewing only
    dass_dep = (dep_score / 100.0) * 42.0
    dass_anx = (anx_score / 100.0) * 42.0
    dass_str = (str_score / 100.0) * 42.0

    hidden_frame = tk.Frame(root, bg="#EAECEE", borderwidth=1, relief=tk.SUNKEN)
    # Hidden completely off-screen at y=480. Drag window down to reveal.
    hidden_frame.place(x=0, y=480, width=650, height=60)
    
    debug_font = tkfont.Font(family="Helvetica", size=9, weight="bold")
    tk.Label(hidden_frame, text="Backend DASS-21 Score Equivalents (Max 42)", font=debug_font, bg="#EAECEE", fg="#7F8C8D").pack(pady=(5, 0))
    
    score_text = f"Depression: {dass_dep:.1f} / 42    |    Anxiety: {dass_anx:.1f} / 42    |    Stress: {dass_str:.1f} / 42"
    tk.Label(hidden_frame, text=score_text, font=tkfont.Font(family="Helvetica", size=10), bg="#EAECEE", fg="#2C3E50").pack()

    root.mainloop()
    
    return user_choice["action"], result_path


def show_loading_ui(result_path):
    root = tk.Tk()
    root.title("Processing...")
    root.geometry("650x480")
    root.resizable(False, False)
    root.configure(bg="#FFFFFF")
    
    tk.Label(root, text="Uploading to Secure Cloud...\nPlease wait.", font=("Helvetica", 16, "bold"), bg="#FFFFFF", fg="#2C3E50").pack(expand=True)
    root.update()

    urls = upload_to_cloudinary(result_path) 
    root.destroy()
    return urls


def show_qr_ui(qr_payload_string):
    root = tk.Tk()
    root.title("Save Your Results")
    root.geometry("650x480") 
    root.resizable(False, False)
    root.configure(bg="#FFFFFF")

    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(qr_payload_string)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white")
    tk_img = ImageTk.PhotoImage(qr_img)

    tk.Label(root, text="Scan to save to Profile", font=("Helvetica", 18, "bold"), bg="#FFFFFF", fg="#2C3E50").pack(pady=(30, 10))
    
    img_label = tk.Label(root, image=tk_img, bg="#FFFFFF")
    img_label.image = tk_img 
    img_label.pack()

    tk.Label(root, text="( Tap anywhere on screen to finish )", font=("Helvetica", 12), bg="#FFFFFF", fg="#7F8C8D").pack(pady=20)

    def close_window(event):
        root.destroy()

    root.bind_all("<Button-1>", close_window)
    root.mainloop()


# ==========================================
# 5. MAIN CAMERA LOOP
# ==========================================
camera_tapped = False

def camera_click_event(event, x, y, flags, param):
    global camera_tapped
    if event == cv2.EVENT_LBUTTONDOWN:  
        camera_tapped = True

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

    # Keep the camera 'hot' outside the loop so it doesn't take 3 seconds to turn on every time
    cap = cv2.VideoCapture(0)
    
    print("\n========================================")
    print(" THESIS KIOSK ACTIVE")
    print(" - Press 'q' on the camera window to safely quit")
    print("========================================\n")

    # --- OUTER LOOP: Manages the Kiosk Flow (Next User in line) ---
    while True:
        # 1. Ensure OpenCV windows are hidden when showing Tkinter
        cv2.destroyAllWindows() 
        
        # 2. Show Privacy Notice (Blocks until user taps)
        show_privacy_notice()

        # 3. Setup OpenCV Window for scanning
        cv2.namedWindow('Thesis Camera')
        cv2.setMouseCallback('Thesis Camera', camera_click_event)
        camera_tapped = False # Reset tap flag for new user

        quit_system = False

        # --- INNER LOOP: The actual camera feed ---
        while True:
            ret, frame = cap.read()
            if not ret: break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
            
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 255), 2)
                cv2.putText(frame, "Tap screen to Scan", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            cv2.imshow('Thesis Camera', frame)

            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'): 
                quit_system = True # Set flag to break both loops
                break
                
            elif key == 32 or camera_tapped: 
                camera_tapped = False 
                
                gray_cap = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces_cap = face_cascade.detectMultiScale(gray_cap, scaleFactor=1.3, minNeighbors=5)

                if len(faces_cap) > 0:
                    clean_frame = frame.copy() 
                    x, y, w, h = faces_cap[0] 
                    
                    face_crop = frame[y:y+h, x:x+w]
                    face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
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

                    # 4. Hide camera while processing UI
                    cv2.destroyAllWindows()

                    # 5. Show Results UI 
                    action, result_path = show_results_ui(dep_score, anx_score, str_score, clean_frame)

                    # 6. Process choice
                    if action == "qr" and result_path:
                        urls = show_loading_ui(result_path)
                        
                        qr_data = {
                            "dep": round(float(dep_score), 1),
                            "anx": round(float(anx_score), 1),
                            "str": round(float(str_score), 1),
                            "result_url": urls.get("result", "") 
                        }
                        qr_string = json.dumps(qr_data)
                        show_qr_ui(qr_string)
                    
                    elif action == "local":
                        print("Results saved locally. Proceeding to next user.")
                    
                    elif action == "discard":
                        print("Results discarded. Proceeding to next user.")

                    # 7. BREAK THE INNER LOOP -> Restart at the Privacy Notice
                    break

        # Check if the user pressed 'q' to shut down the whole system
        if quit_system:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()