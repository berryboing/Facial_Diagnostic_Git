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
# TODO: Replace these with your actual keys from the Cloudinary Dashboard
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
def upload_to_cloudinary(face_path, result_path):
    urls = {"face": None, "result": None}
    try:
        print("Uploading Face to Cloudinary...")
        face_resp = cloudinary.uploader.upload(face_path, folder="thesis_faces")
        urls["face"] = face_resp['secure_url']
        
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
def show_results_ui(dep_score, anx_score, str_score, captured_frame):
    root = tk.Tk()
    root.title("Facial Scanning Report")
    root.geometry("650x480") 
    root.resizable(False, False) # Lock the window size
    root.configure(bg="#FFFFFF") 

    user_choice = {"action": "skip"} # Default action

    title_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
    body_font = tkfont.Font(family="Helvetica", size=10)
    btn_font = tkfont.Font(family="Helvetica", size=11, weight="bold")
    
    text_dark = "#2C3E50"  
    bg_gray = "#F8F9F9"    

    notice_statement = "NOTICE: This is just an initial assessment using facial scanning technology and is not a clinical diagnosis."
    tk.Label(root, text=notice_statement, font=tkfont.Font(family="Helvetica", size=9, slant="italic"), bg="#FFFFFF", fg="#E67E22").pack(pady=(10, 0))
    tk.Label(root, text="Initial Assessment Results", font=title_font, bg="#FFFFFF", fg=text_dark).pack(pady=(10, 5))

    # --- DYNAMIC TEXT LOGIC ---
    slight_list, increased_list = [], []
    if 36.0 <= dep_score < 71.0: slight_list.append("depression")
    elif dep_score >= 71.0: increased_list.append("depression")

    if 36.0 <= anx_score < 71.0: slight_list.append("anxiety")
    elif anx_score >= 71.0: increased_list.append("anxiety")

    if 36.0 <= str_score < 71.0: slight_list.append("stress")
    elif str_score >= 71.0: increased_list.append("stress")

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
    text_frame.pack(fill=tk.X, expand=False, padx=30, pady=10)
    tk.Label(text_frame, text=main_text, font=body_font, bg=bg_gray, fg=text_dark, wraplength=560, justify=tk.LEFT).pack(anchor="w")

    # ==========================================
    # --- FIX: FORCE WINDOW TO FRONT & PAUSE ---
    # ==========================================
    root.attributes('-topmost', True) # Force the window above all other apps
    root.update_idletasks()           # Calculate exact window sizes
    root.update()                     # Force the OS to draw the window
    time.sleep(0.5)                   # Wait half a second for the screen to catch up

    # --- 1. LOCAL SAVE & CROPPED SCREENSHOT ---
    save_dir = "snapshots"
    if not os.path.exists(save_dir): os.makedirs(save_dir)
    timestamp = int(time.time())
    
    face_path = os.path.join(save_dir, f"face_{timestamp}.jpg")
    result_path = os.path.join(save_dir, f"result_{timestamp}.jpg")
    cv2.imwrite(face_path, captured_frame)
    
    try:
        x = root.winfo_rootx()
        y = root.winfo_rooty()
        w = root.winfo_width()
        # Crop exactly at the bottom of the text frame
        crop_y_bottom = text_frame.winfo_rooty() + text_frame.winfo_height() + 15 
        ImageGrab.grab(bbox=(x, y, x + w, crop_y_bottom)).save(result_path)
    except Exception as e:
        print(f"Screenshot Error: {e}")

    root.attributes('-topmost', False) # Let the window behave normally again
    # ==========================================


    # --- 2. TOUCH BUTTONS (Added AFTER the screenshot is taken) ---
    btn_frame = tk.Frame(root, bg="#FFFFFF")
    btn_frame.pack(fill=tk.X, pady=(15, 0))
    
    # ... (rest of your button code remains exactly the same) ...

    def on_generate_qr():
        user_choice["action"] = "qr"
        root.destroy()

    def on_skip():
        user_choice["action"] = "skip"
        root.destroy()

    # Layout for large, touch-friendly buttons
    skip_btn = tk.Button(btn_frame, text="Skip\n(Local Save Only)", font=btn_font, bg="#E74C3C", fg="white", width=18, pady=8, command=on_skip)
    skip_btn.pack(side=tk.LEFT, padx=(30, 10))

    qr_btn = tk.Button(btn_frame, text="Generate QR\n(Save to Web App)", font=btn_font, bg="#27AE60", fg="white", width=18, pady=8, command=on_generate_qr)
    qr_btn.pack(side=tk.RIGHT, padx=(10, 30))

    root.mainloop()
    
    return user_choice["action"], face_path, result_path


def show_loading_ui(face_path, result_path):
    # This keeps the screen busy while uploading to Cloudinary
    root = tk.Tk()
    root.title("Processing...")
    root.geometry("650x480")
    root.resizable(False, False)
    root.configure(bg="#FFFFFF")
    
    tk.Label(root, text="Uploading to Secure Cloud...\nPlease wait.", font=("Helvetica", 16, "bold"), bg="#FFFFFF", fg="#2C3E50").pack(expand=True)
    root.update()

    urls = upload_to_cloudinary(face_path, result_path)
    root.destroy()
    return urls


def show_qr_ui(qr_payload_string):
    root = tk.Tk()
    root.title("Save Your Results")
    root.geometry("650x480") # Matched size explicitly
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

    cap = cv2.VideoCapture(0)
    
    cv2.namedWindow('Thesis Camera')
    cv2.setMouseCallback('Thesis Camera', camera_click_event)

    print("\n========================================")
    print(" THESIS CAMERA ACTIVE")
    print(" - Tap the video feed window to scan")
    print(" - Press 'q' to quit")
    print("========================================\n")

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

                # 1. Show UI (Saves locally automatically, waits for user button tap)
                action, face_path, result_path = show_results_ui(dep_score, anx_score, str_score, clean_frame)

                # 2. If user tapped "Generate QR", process the Cloud upload and show QR
                if action == "qr":
                    urls = show_loading_ui(face_path, result_path)
                    
                    qr_data = {
                        "dep": round(float(dep_score), 1),
                        "anx": round(float(anx_score), 1),
                        "str": round(float(str_score), 1),
                        "face_url": urls.get("face", ""),
                        "result_url": urls.get("result", "")
                    }
                    qr_string = json.dumps(qr_data)
                    show_qr_ui(qr_string)
                
                # If action == "skip", it just loops back to the camera (already saved locally!)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()