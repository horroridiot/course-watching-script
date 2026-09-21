"""
学习通自动化助手 (Chaoxing Automation Helper)
==============================================
本项目基于 Playwright 和 OpenAI 兼容接口，用于自动化处理学习通课程任务。
支持：自动播放视频、自动答题（AI）、多视频章节防跳、防死循环。

依赖安装：
    py -m pip install playwright openai -i https://pypi.tuna.tsinghua.edu.cn/simple
    py -m playwright install

运行方式：
    py run.py

注意：
    1. 请务必在终端提示时输入自己的智谱 API Key 和课程链接。
    2. 本脚本仅供学习交流使用，请遵守相关平台规则。
"""

import sys
import time
import re
import functools
from playwright.sync_api import sync_playwright
from openai import OpenAI

# 强制终端 UTF-8 编码，解决中文报错
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

# 强制 print 立即输出
print = functools.partial(print, flush=True)

# ==================== 配置区 ====================
# 请在运行脚本时根据提示输入以下信息（不再硬编码，方便开源）
API_KEY = "API KEY"
BASE_URL = "模型提供地址"
MODEL = "模型名称"  # 免费模型，速度快

COURSE_URL = "课程链接"
# =================================================

client = None

def chapter_to_num(chap_str):
    try:
        parts = chap_str.split('.')
        if len(parts) == 2:
            return int(parts[0]) * 100 + int(parts[1])
        return int(chap_str) * 100
    except:
        return 0

def get_ai_answer(question_text, options, q_type="单选题"):
    if "填空" in q_type:
        prompt = f"你是答题助手。请给出以下题目的填空答案，如果有多个空，请用|||分隔，不要解释。\n题目：{question_text}"
    else:
        prompt = f"你是答题助手。请给出以下题目的正确答案。\n类型：{q_type}\n题目：{question_text}\n选项：{options}\n要求：只返回字母（如A），多选用逗号分隔（如A,C），判断题返回正确或错误。不要解释。"
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [API调用失败] {e}")
        return None

def close_popups(page):
    try:
        for f in page.frames:
            for text in ["知道了", "确定", "关闭"]:
                btn = f.get_by_text(text, exact=True)
                if btn.count() > 0:
                    btn.first.click()
                    time.sleep(1)
                    return
    except: pass

def handle_quiz(page):
    quiz_frame = None
    for f in page.frames:
        try:
            if f.locator(".TiMu").count() > 0 or f.locator(".questionLi").count() > 0:
                quiz_frame = f
                break
        except: pass
    if not quiz_frame: return False

    questions = quiz_frame.locator(".TiMu").all() or quiz_frame.locator(".questionLi").all()
    if not questions: return False

    print(f"  [发现测验] 共 {len(questions)} 道题目，调用AI答题...")
    for i, q in enumerate(questions):
        try:
            q_type_el = q.locator(".newZy_TItle, .mark_name").first
            q_type = q_type_el.inner_text().strip() if q_type_el.count() > 0 else "单选题"
            q_text_el = q.locator(".clearfix, .Zy_TItle").first
            q_text = q_text_el.inner_text().strip() if q_text_el.count() > 0 else ""
            
            if "填空" in q_type or q.locator("input[type='text'], textarea").count() > 0:
                inputs = q.locator("input[type='text'], textarea").all()
                if inputs:
                    ai_answer = get_ai_answer(q_text, [], q_type="填空题")
                    if ai_answer:
                        answers = ai_answer.split("|||")
                        for j, inp in enumerate(inputs):
                            if j < len(answers):
                                inp.fill(answers[j].strip())
                                time.sleep(0.3)
                    print(f"    第{i+1}题 [填空] -> AI填入完毕")
                continue

            option_els = q.locator("li").all()
            options = [opt.inner_text().strip() for opt in option_els if opt.inner_text().strip()]
            if options:
                ai_answer = get_ai_answer(q_text, options, q_type)
                if ai_answer:
                    answer_letters = re.findall(r'[A-Z]', ai_answer.upper())
                    if answer_letters:
                        for letter in answer_letters:
                            idx = ord(letter) - ord('A')
                            if 0 <= idx < len(option_els):
                                option_els[idx].click()
                                time.sleep(0.3)
                    else:
                        for opt in option_els:
                            if ai_answer in opt.inner_text():
                                opt.click()
                                break
                    print(f"    第{i+1}题 [{q_type}] -> AI选择 {ai_answer}")
            time.sleep(1)
        except Exception as e:
            print(f"    处理第{i+1}题出错: {e}")

    try:
        submit_btn = quiz_frame.locator("text='提交'").first
        if submit_btn.count() > 0:
            submit_btn.click()
            print("  [测验] 已点击初次提交")
            time.sleep(2)
            
            confirm_btn = page.locator(".layui-layer-btn0")
            if confirm_btn.count() > 0:
                confirm_btn.first.click()
                print("  [测验] 已点击弹窗确认(.layui-layer-btn0)")
                time.sleep(2)
            else:
                confirmed = False
                for f in page.frames:
                    for btn_text in ["提交", "确定", "确认"]:
                        c_btn = f.get_by_text(btn_text, exact=True)
                        if c_btn.count() > 0:
                            c_btn.first.click()
                            print(f"  [测验] 已点击弹窗中的'{btn_text}'")
                            confirmed = True
                            time.sleep(2)
                            break
                    if confirmed:
                        break
    except Exception as e:
        print(f"  提交测验出错: {e}")

    return True

def handle_document(page):
    print("  [检测文档] 正在尝试阅读...")
    try:
        for f in page.frames:
            if f.locator(".pdf, .doc, .text-content, #pdfContainer, .reader").count() > 0:
                for _ in range(5):
                    f.evaluate("window.scrollBy(0, 500);")
                    time.sleep(1)
                f.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                print("  [文档] 模拟阅读翻页完成")
                return True
    except: pass
    return False

def process_chapter(page, chapter_num, played_src):
    print(f"  [开始处理章节 {chapter_num}...]")
    handle_quiz(page)
    
    chapter_failed = False

    for round_num in range(5):
        print(f"\n  [{chapter_num} 第 {round_num + 1} 轮扫描]")
        time.sleep(5)
        
        target_video = None
        target_frame = None
        
        for f in page.frames:
            try:
                videos = f.locator("video").all()
                for v in videos:
                    try:
                        if not v.is_visible(): continue
                            
                        src = v.evaluate("v => v.currentSrc || v.src || ''")
                        if src and src in played_src:
                            continue
                            
                        curr = v.evaluate("v => v.currentTime") or 0
                        dur = v.evaluate("v => v.duration") or 0
                        
                        if dur == 0:
                            for _ in range(10):
                                time.sleep(1)
                                dur = v.evaluate("v => v.duration") or 0
                                if dur > 0: break
                                
                        if dur > 0 and curr >= dur - 5:
                            if src: played_src.add(src)
                            continue
                            
                        target_video = v
                        target_frame = f
                        break
                    except: continue
            except: pass
            if target_video: break
            
        if not target_video:
            print(f"  [{chapter_num} 所有视频均已处理完毕]")
            break
            
        print(f"  🔥 [发现 {chapter_num} 的未完成视频] 强制播放...")
        chapter_failed = True
        src = target_video.evaluate("v => v.currentSrc || v.src || ''")
        
        try:
            target_video.scroll_into_view_if_needed()
            time.sleep(1)
            
            click_success = False
            for btn in [".vjs-big-play-button", ".vjs-play-control", "button[title='播放']"]:
                if target_frame.locator(btn).count() > 0:
                    try:
                        target_frame.locator(btn).first.click(timeout=5000, force=True)
                        click_success = True
                        break
                    except Exception as e:
                        print(f"  [物理点击超时，尝试 JS 强制播放]")
            
            target_video.evaluate("v => { v.muted = true; v.playbackRate = 1.5; v.play().catch(e => {}); }")
            
        except Exception as e:
            print(f"  [播放操作异常] {e}")
            continue
            
        last_time = target_video.evaluate("v => v.currentTime") or 0
        stalled = 0
        completed = False
        
        while True:
            time.sleep(5)
            try:
                curr = target_video.evaluate("v => v.currentTime") or 0
                dur = target_video.evaluate("v => v.duration") or 1
                paused = target_video.evaluate("v => v.paused")
                
                if paused:
                    target_video.evaluate("v => v.play().catch(e => {})")
                    
                if curr >= dur - 2 and dur > 10:
                    print(f"  ✅ [{chapter_num} 视频进度100%] 等待服务器同步...")
                    time.sleep(10)
                    completed = True
                    break
                    
                if abs(curr - last_time) < 0.5:
                    stalled += 1
                    if stalled > 6:
                        print("  ⚠️ [视频卡死超过30秒，跳过此视频，标记章节需重试]")
                        break
                else:
                    stalled = 0
                last_time = curr
            except Exception as e:
                print(f"  [监控异常] {e}")
                break
                
        if completed:
            chapter_failed = False
            if src: 
                played_src.add(src)
                
    handle_document(page)
    handle_quiz(page)
    return chapter_failed

def find_next_chapter(page, processed_chapters, start_num=0):
    valid_chapters = []
    for f in page.frames:
        try:
            links = f.locator("a, li").all()
            for link in links:
                try:
                    text = link.inner_text()
                    match = re.search(r'(\d+\.\d+)', text)
                    if match:
                        chapter_num = match.group(1)
                        if chapter_num in processed_chapters: continue
                        if start_num > 0 and chapter_to_num(chapter_num) < start_num: continue
                        valid_chapters.append((chapter_num, link, text))
                except: continue
        except: pass
    
    valid_chapters.sort(key=lambda x: chapter_to_num(x[0]))
    
    if valid_chapters:
        return valid_chapters[0][1], valid_chapters[0][0], valid_chapters[0][2]
    return None, None, None

def run():
    global API_KEY, COURSE_URL, client
    
    print("=" * 60)
    print("          学习通自动化助手 (Chaoxing Automation Helper)")
    print("=" * 60)
    print("提示：本项目已开源，不包含任何个人信息。请在使用时输入自己的信息。")
    print("-" * 60)
    
    # 1. 获取 API Key
    if not API_KEY:
        API_KEY = input("👉 请输入你的智谱 API Key（输入后按回车）: ").strip()
        
    # 2. 获取课程链接
    if not COURSE_URL:
        COURSE_URL = input("👉 请输入你的学习通课程链接（输入后按回车）: ").strip()
        
    if not API_KEY or not COURSE_URL:
        print("❌ 错误：API Key 或 课程链接 不能为空，脚本退出！")
        return
        
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("\n[1/3] 正在打开学习通登录页...")
        try: 
            page.goto("https://passport2.chaoxing.com/login?fid=&refer=http://i.mooc.chaoxing.com")
        except Exception as e: 
            print(f"打开登录页失败: {e}")

        print("\n👉【重要】请在浏览器中手动扫码或输入账号密码登录！")
        input("👉 登录成功并看到个人主页后，请回到终端按【回车键】继续...")

        print("\n[2/3] 正在打开课程页面...")
        try: 
            page.goto(COURSE_URL)
        except Exception as e:
            print(f"❌ 打开课程链接失败: {e}")
            browser.close()
            return

        time.sleep(8)
        
        start_input = input("\n👉 [3/3] 请输入你想从哪一章开始（例如 2.1，如果从头开始请直接回车）: ").strip()
        start_num = chapter_to_num(start_input) if start_input else 0
        
        visited_chapters = set()
        failed_chapters = {}
        played_src = set()
        
        no_task_count = 0
        while True:
            time.sleep(3)
            task_link, chapter_num, task_text = find_next_chapter(page, visited_chapters, start_num)

            if not task_link:
                no_task_count += 1
                print(f"\n暂未检测到新的未完成章节 ({no_task_count}/5)...")
                if no_task_count >= 5:
                    print("连续多次未找到新章节，脚本结束。")
                    break
                try: page.goto(COURSE_URL)
                except: pass
                time.sleep(5)
                continue

            no_task_count = 0
            visited_chapters.add(chapter_num) 
            print(f"\n================ 进入大章节: {task_text.strip()} ================")
            
            try: task_link.click()
            except: continue
                
            print("  [等待页面和视频加载中...]")
            time.sleep(12)

            all_pages = context.pages
            if len(all_pages) > 1:
                page = all_pages[-1] 
                print("  [切换至新标签页]")
                time.sleep(5)

            close_popups(page)
            
            failed = process_chapter(page, chapter_num, played_src)
            if failed:
                failed_chapters[chapter_num] = 1

            if len(context.pages) > 1:
                page.close()
                page = context.pages[0]
            
            print("准备返回目录寻找下一个章节...")
            try: page.goto(COURSE_URL)
            except: pass
            time.sleep(5)

        if failed_chapters:
            print("\n" + "="*50)
            print(f"⚠️ 检测到 {len(failed_chapters)} 个章节未彻底完成，开始重试...")
            print("="*50)
            
            for chapter_num in list(failed_chapters.keys()):
                if failed_chapters[chapter_num] >= 3:
                    print(f"⛔ 章节 {chapter_num} 失败次数过多，放弃重试，请手动检查！")
                    continue
                    
                print(f"\n🔄 正在重试章节 {chapter_num} (第 {failed_chapters[chapter_num] + 1} 次)...")
                
                target_link = None
                for f in page.frames:
                    try:
                        links = f.locator("a, li").all()
                        for link in links:
                            if chapter_num in link.inner_text():
                                target_link = link
                                break
                    except: continue
                    if target_link: break
                
                if not target_link:
                    print(f"❌ 无法找到章节 {chapter_num} 的链接，跳过。")
                    continue
                    
                target_link.click()
                time.sleep(12)
                
                all_pages = context.pages
                if len(all_pages) > 1:
                    page = all_pages[-1] 
                    time.sleep(5)
                    
                close_popups(page)
                failed = process_chapter(page, chapter_num, played_src)
                
                if failed:
                    failed_chapters[chapter_num] += 1
                else:
                    del failed_chapters[chapter_num]
                    
                if len(context.pages) > 1:
                    page.close()
                    page = context.pages[0]
                    
                try: page.goto(COURSE_URL)
                except: pass
                time.sleep(5)

        print("\n所有可识别的章节处理完毕！浏览器将在10秒后关闭。")
        time.sleep(10)
        browser.close()

if __name__ == "__main__":
    run()
