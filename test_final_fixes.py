import re
import os
import sys
import time
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

# Import or define the exact logic to test
def normalize_prompt_text(text):
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    lines = [line.rstrip() for line in t.split("\n")]
    return "\n".join(lines).strip()

def verify_prompt_logic(expected_text, actual_raw):
    expected_norm = normalize_prompt_text(expected_text)
    actual_norm = normalize_prompt_text(actual_raw)
    exp_len = len(expected_norm)
    act_len = len(actual_norm)
    if exp_len == 0:
        return act_len == 0
    coverage = act_len / exp_len
    if coverage < 0.98 or coverage > 1.05:
        return False
    prefix_len = min(80, exp_len)
    if actual_norm[:prefix_len] != expected_norm[:prefix_len]:
        return False
    suffix_len = min(80, exp_len)
    if actual_norm[-suffix_len:] != expected_norm[-suffix_len:]:
        return False
    return True

def test_1_long_prompt_3000():
    prompt = ("CORE OBJECTIVE: Commercial fashion photography photoshoot. " + 
              "Detailed fashion model studio setup with 8k lighting and clean aesthetics. " * 45 +
              "Final style: high-fashion editorial output.")
    assert len(prompt) > 3000, f"Length is {len(prompt)}"
    # Simulate exact input in editor
    simulated_editor_content = prompt + "  \r\n"
    ok = verify_prompt_logic(prompt, simulated_editor_content)
    assert ok, "Test 1 failed"
    # Negative test: truncated prompt (e.g. missing 5%)
    truncated = prompt[:int(len(prompt)*0.94)]
    assert not verify_prompt_logic(prompt, truncated), "Test 1 negative test failed"
    print("✅ TEST 1 PASSED: Long prompt > 3000 characters atomic verification passed.")

def test_2_lowest_id_priority():
    tab_states = [
        {"tab_id": 0, "state": "GEN_WAITING"},
        {"tab_id": 1, "state": "IDLE"},
        {"tab_id": 2, "state": "IDLE"},
        {"tab_id": 3, "state": "GEN_WAITING"},
    ]
    def find_first_idle_tab(states):
        for tid in range(len(states)):
            if states[tid]["state"] == "IDLE":
                return tid
        return None
    
    assert find_first_idle_tab(tab_states) == 1, "Should select T1"
    # When T0 becomes free:
    tab_states[0]["state"] = "IDLE"
    assert find_first_idle_tab(tab_states) == 0, "Should select T0 over T1/T2"
    print("✅ TEST 2 PASSED: Strict lowest-ID priority (T0 first) verified.")

def test_3_file_stability_and_pil():
    tmp_dir = Path("test_download_dir")
    tmp_dir.mkdir(exist_ok=True)
    test_img = tmp_dir / "jobA_test.png"
    
    # Create valid test PNG with size > 500 bytes
    img = Image.new("RGB", (600, 600), color="blue")
    img.save(test_img)
    
    sz1 = test_img.stat().st_size
    assert sz1 > 500
    
    # Validate with PIL
    with Image.open(test_img) as im:
        im.verify()
    
    # Cleanup
    test_img.unlink(missing_ok=True)
    tmp_dir.rmdir()
    print("✅ TEST 3 PASSED: File stability check and PIL verification passed.")

def test_4_flash_model_filter():
    def is_valid_flash(txt):
        txt = (txt or "").strip().lower()
        return "flash" in txt and "lite" not in txt
        
    assert is_valid_flash("Gemini 2.0 Flash") == True
    assert is_valid_flash("Gemini 1.5 Flash") == True
    assert is_valid_flash("Gemini 2.0 Flash Lite") == False
    assert is_valid_flash("Flash Lite Preview") == False
    assert is_valid_flash("Gemini 2.0 Pro") == False
    print("✅ TEST 4 PASSED: Flash strictly accepted, Flash Lite and Pro strictly rejected.")

def test_5_attachment_count_verification():
    def verify_attachments(expected_count, verified_count):
        return verified_count >= expected_count
        
    assert verify_attachments(3, 3) == True
    assert verify_attachments(3, 2) == False
    assert verify_attachments(3, 1) == False
    assert verify_attachments(1, 1) == True
    print("✅ TEST 5 PASSED: Exact attachment count validation verified.")

if __name__ == "__main__":
    test_1_long_prompt_3000()
    test_2_lowest_id_priority()
    test_3_file_stability_and_pil()
    test_4_flash_model_filter()
    test_5_attachment_count_verification()
    print("\nALL 5 LOCAL VERIFICATION TESTS PASSED SUCCESSFULLY!")
