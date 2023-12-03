#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64, json, re, requests, os, argparse

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


# 常量
MIUI_UPDATE_URL = "https://update.miui.com/updates/miotaV3.php"
IV = b"0102030405060708"


# 生成上传数据
def generate_json(device, version, android, userId):
    data = {  # After testing, the commented out parts do not need to be assigned values.
        # "obv": "OS1.0", # ro.mi.os.version.name
        # "channel":"",  # Unknown
        # "sys": "0",  # Unknown
        # "bv": "816",  # bigversion
        "id": userId,  # userId
        # "sn": "0x0000000000000000",  # SN
        # "a": "0",  # Unknown
        # "b": "F" if "DEV" not in version else "X",  # MIUI branch
        "c": android,  # android version Build.VERSION.RELEASE
        # "unlock": "0",  # 1: bootloader is unlocked. 0: bootloader locked.
        "d": device,  # PRODUCT_DEVICE
        # "lockZoneChannel": "",  # Unknown
        "f": "1",  # Unknown, necessary
        "ov": version,  # ro.mi.os.version.incremental
        # "g": "00000000000000000000000000000000",  # Unknown, 32
        # "i": "0000000000000000000000000000000000000000000000000000000000000000",  # Unknown, 64
        # "i2": "0000000000000000000000000000000000000000000000000000000000000000",  # Unknown, 64
        # "isR": "0",  # ro.debuggable
        "l": "zh_CN" if "_global" not in device else "en_US",  # The locale. (for changelog)
        # "n": "ct",  # ro.carrier.name
        # "p": device,  # PRODUCT_DEVICE
        # "pb": "Xiaomi",  # "Redmi", PRODUCT_BRAND
        "r": "CN" if "_global" not in device else "GL",  # Sales regions. (for changelog)
        # MIUI version "MIUI-" + Build.VERSION.INCREMENTAL
        "v": f"miui-{version.replace('OS1', 'V816')}",
        # "sdk": "34" if android == "14" else "33",  # Android SDK
        # "pn": device,  # PRODUCT_NAME
        # "options": {
        # "zone": "1" if "_global" not in device else "2",  # ro.rom.zone
        # "hashId":"0000000000000000",
        # "ab": "1",  # Whether to support A/B update
        # "previewPlan": "0",
        # "sv": 3,
        # "av": "8.4.0", # com.android.update application version
        # "cv": version.replace('OS1', 'V816')
        # }
    }
    return json.dumps(data).replace(" ", "").replace("'", '"')


# AES加密
def miui_encrypt(json_request, securityKey):
    cipher = AES.new(securityKey, AES.MODE_CBC, IV)
    padded_text = pad(json_request.encode("utf-8"), cipher.block_size)
    encrypted_text = cipher.encrypt(padded_text)
    return base64.urlsafe_b64encode(encrypted_text).decode("utf-8")


# AES解密
def miui_decrypt(encrypted_text, securityKey):
    cipher = AES.new(securityKey, AES.MODE_CBC, IV)
    encrypted_text_bytes = base64.urlsafe_b64decode(encrypted_text)
    decrypted_text = cipher.decrypt(encrypted_text_bytes)
    unpadded_text = unpad(decrypted_text, cipher.block_size).decode("utf-8")
    return json.loads(unpadded_text)


# 获取返回参数
def request(data):
    try:
        response = requests.post(url=MIUI_UPDATE_URL, data=data)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"向服务器发送请求时出错: {e}")
        return None


def parse_rom_branch(rom_branch):
    branch_descriptions = {
        "F": "正式版 (每月构建, 末尾数字不为 0 的为内部测试构建)",
        "X": "开发版 (每周构建)",
        "D": "开发版内测 (每日构建, 有时候会转到开发版)",
        "T": "绝密版 (曾经的内测版及未通过测试的版本)",
        "I": "内部构建 (内部测试使用, 有时候会转到开发版)",
    }
    return branch_descriptions.get(rom_branch, "其他版本")


# 分析返回参数
def choose(name, interface):
    interface_version = "v1" if interface == "1" else "v2"

    current_rom_info = name.get("CurrentRom", {})
    rom_device = current_rom_info.get("device", "Unknown")
    rom_version = current_rom_info.get("version", "Unknown")
    rom_codebase = current_rom_info.get("codebase", "Unknown")
    rom_md5 = current_rom_info.get("md5", "Unknown")
    rom_filename = current_rom_info.get("filename", "Unknown")
    rom_filesize = current_rom_info.get("filesize", "Unknown")
    rom_bigversion = ("HyperOS 1.0" if current_rom_info.get("bigversion") == "816" else current_rom_info.get("bigversion", "Unknown"))
    rom_branch = parse_rom_branch(current_rom_info.get("branch", "Unknown"))
    rom_changelog = re.sub(
        r"\n\s*\n",
        "\n",
        json.dumps(current_rom_info.get("changelog", "Unknown"), indent=2, ensure_ascii=False, allow_nan=True,)
        .replace("[", "")
        .replace("]", "")
        .replace("{", "")
        .replace("}", "")
        .replace('"', "")
        .replace("txt:", ""),
    )

    latset_rom_info = name.get("LatestRom", {})
    latset_rom_md5 = latset_rom_info.get("md5", "Unknown")
    latset_rom_filename = latset_rom_info.get("filename", "Unknown")

    if rom_version == "Unknown":
        result = "\n\n未获取到相关 ROM 信息\n\n"
    elif rom_filename == "Unknown":
        result = f"\ndevice: {rom_device}\nversion: {rom_version}\ncodebase: Android {rom_codebase}\nbranch: {rom_branch}\ninterface: {interface_version}\n"
    elif rom_md5 == latset_rom_md5:
        result = f"\ndevice: {rom_device}\nversion: {rom_version}\nbigversion: {rom_bigversion}\ncodebase: Android {rom_codebase}\nbranch: {rom_branch}\ninterface: {interface_version}\n\nfilename: {rom_filename}\nfilesize: {rom_filesize}\ndownload: https://ultimateota.d.miui.com/{rom_version}/{latset_rom_filename}\nchangelog:\n{rom_changelog}\n"
    else:
        result = f"\ndevice: {rom_device}\nversion: {rom_version}\nbigversion: {rom_bigversion}\ncodebase: Android {rom_codebase}\nbranch: {rom_branch}\ninterface: {interface_version}\n\nfilename: {rom_filename}\nfilesize: {rom_filesize}\ndownload: https://bigota.d.miui.com/{rom_version}/{rom_filename}\nchangelog:\n{rom_changelog}\n"

    print(result)


# 使用提示
def parse_arguments():
    parser = argparse.ArgumentParser(description="Xiaomi Update Info")
    parser.add_argument("codename", help="Device codename")
    parser.add_argument("rom_version", help="ROM version")
    parser.add_argument("android_version", help="Android version")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    return parser.parse_args()


# 主程序
def main():
    args = parse_arguments()
    userId = ""
    serviceToken = ""
    interface = "1"
    securityKey = b"miuiotavalided11"
    if os.path.isfile("cookies.json"):
        with open("cookies.json", "r", encoding="utf-8") as file:
            cookies = json.load(file)
            userId = cookies["userId"]
            securityKey = base64.b64decode(cookies["ssecurity"])
            serviceToken = cookies["serviceToken"]
    json_data = generate_json(args.codename, args.rom_version, args.android_version, userId)
    encrypted_text = miui_encrypt(json_data, securityKey)
    if serviceToken != "":
        interface = "2"
    post_data = {"q": encrypted_text, "t": serviceToken, "s": interface}
    requested_encrypted_text = request(post_data)
    requested_decrypted_text = miui_decrypt(requested_encrypted_text, securityKey)
    if args.verbose == True:
        print(requested_decrypted_text)
    else:
        choose(requested_decrypted_text, interface)


if __name__ == "__main__":
    main()
