import os
import zipfile
import shutil
import sys

def patch_app(base_library_path, app_root):
    if not os.path.exists(base_library_path):
        print(f"[-] Loi: Khong tim thay file thu vien: {base_library_path}")
        return False

    print(f"[*] Dang va loi cho file: {base_library_path}")
    
    # Tao ban backup
    backup_path = base_library_path + ".backup"
    if not os.path.exists(backup_path):
        shutil.copy2(base_library_path, backup_path)
        print(f"[+] Da tao backup tai: {backup_path}")

    # Danh sach cac thu muc trong app can dua vao zip
    modules_to_add = [
        ("app/services", "services"),
        ("app/engines", "engines"),
        ("app/workflows", "workflows"),
        ("app/layers", "layers"),
        ("app/core", "core"),
        ("app/translation", "translation"),
        ("app/utils", "utils"),
        ("ui/controllers", "controllers"),
        ("ui/features", "features"),
        ("ui/dialogs", "dialogs"),
        ("ui/helpers", "helpers"),
        ("ui/views", "views"),
        ("ui/widgets", "widgets"),
        ("ui/worker_adapters", "worker_adapters"),
        ("ui/utils", "ui/utils"),
    ]
    
    standalone_files = [
        ("app/ocr_processor.py", "ocr_processor.py"),
        ("app/sensevoice_processor.py", "sensevoice_processor.py"),
        ("app/vad_processor.py", "vad_processor.py"),
        ("app/translator.py", "translator.py"),
        ("app/video_filter_chain.py", "video_filter_chain.py"),
        ("app/new_highlight_selector.py", "new_highlight_selector.py"),
        ("app/audio_waveform.py", "audio_waveform.py"),
        ("app/version.py", "version.py"),
        ("app/runtime_paths.py", "runtime_paths.py"),
        ("app/runtime_profile.py", "runtime_profile.py"),
        ("app/remote_api.py", "remote_api.py"),
        ("app/remote_api_server.py", "remote_api_server.py"),
    ]

    added_count = 0
    with zipfile.ZipFile(base_library_path, 'a', zipfile.ZIP_DEFLATED) as zipf:
        for src_rel_dir, target_pkg in modules_to_add:
            src_full_dir = os.path.join(app_root, src_rel_dir)
            if not os.path.exists(src_full_dir):
                continue
            for root, dirs, files in os.walk(src_full_dir):
                if "__pycache__" in root or ".git" in root:
                    continue
                for f in files:
                    if f.endswith(".py"):
                        file_abs = os.path.join(root, f)
                        rel_to_pkg = os.path.relpath(file_abs, src_full_dir)
                        # Ghi vao package namespace va app.package namespace
                        arc_names = [
                            f"{target_pkg}/{rel_to_pkg}".replace("\\", "/"),
                            f"app/{target_pkg}/{rel_to_pkg}".replace("\\", "/")
                        ]
                        for arc_name in arc_names:
                            zipf.write(file_abs, arcname=arc_name)
                            added_count += 1

        for src_rel_file, target_name in standalone_files:
            file_abs = os.path.join(app_root, src_rel_file)
            if os.path.exists(file_abs):
                arc_names = [
                    target_name,
                    f"app/{target_name}"
                ]
                for arc_name in arc_names:
                    zipf.write(file_abs, arcname=arc_name)
                    added_count += 1

    print(f"[+] Da bo sung {added_count} module vao ban build!")
    print("[+] Hoan tat va loi thanh cong! Ban co the mo lai ung dung.")
    return True

if __name__ == "__main__":
    project_root = os.path.abspath(os.path.dirname(__file__))
    
    print("==============================================")
    print("       CÔNG CỤ VÁ LỖI TOÀN DIỆN VIUSTUDIO      ")
    print("==============================================")
    
    app_dir = input("Nhap duong dan thu muc phan mem da giai nen: ").strip().strip('"')
    if not app_dir:
        default_dist = os.path.join(project_root, "dist", "VIUStudio")
        if not os.path.exists(default_dist):
            default_dist = os.path.join(project_root, "dist", "CapCap")
        if os.path.exists(default_dist):
            app_dir = default_dist
            print(f"[*] Tu dong phat hien thu muc: {app_dir}")

    internal_dir = os.path.join(app_dir, "_internal")
    base_lib = os.path.join(internal_dir, "base_library.zip")
    if not os.path.exists(base_lib):
        base_lib = os.path.join(app_dir, "base_library.zip")
        
    if patch_app(base_lib, project_root):
        input("\nNhan Enter de thoat...")
    else:
        input("\n[!] Va loi that bai. Vui long kiem tra lai duong dan...")
