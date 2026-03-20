import streamlit as st
import time

# =======================================================
# === 针对 Python 3.14 & Pydantic V1 的底层兼容性热修复 ===
# =======================================================
import pydantic.v1.fields
import pydantic.v1.schema
from typing import Any

if not hasattr(pydantic.v1.fields.ModelField, "_orig_set_default_and_type"):
    pydantic.v1.fields.ModelField._orig_set_default_and_type = pydantic.v1.fields.ModelField._set_default_and_type
def _patched_set_default(self):
    try:
        pydantic.v1.fields.ModelField._orig_set_default_and_type(self)
    except Exception:
        self.type_ = Any
        self.outer_type_ = Any
        self.required = False
pydantic.v1.fields.ModelField._set_default_and_type = _patched_set_default

if not hasattr(pydantic.v1.schema, "_orig_get_annotation"):
    pydantic.v1.schema._orig_get_annotation = pydantic.v1.schema.get_annotation_from_field_info
def _patched_get_annotation(*args, **kwargs):
    try:
        return pydantic.v1.schema._orig_get_annotation(*args, **kwargs)
    except Exception:
        return Any
pydantic.v1.schema.get_annotation_from_field_info = _patched_get_annotation

if not hasattr(pydantic.v1.fields.ModelField, "_orig_validate"):
    pydantic.v1.fields.ModelField._orig_validate = pydantic.v1.fields.ModelField.validate
def _patched_validate(self, v, values, *, loc, cls=None):
    if self.type_.__class__.__name__ == "ForwardRef":
        return v, None
    return pydantic.v1.fields.ModelField._orig_validate(self, v, values, loc=loc, cls=cls)
pydantic.v1.fields.ModelField.validate = _patched_validate
# =======================================================

import spacy

st.set_page_config(page_title="算法动画演示", page_icon="🌟", layout="wide")

st.markdown("# 🌟 依存句法：转移算法 (Transition-based) 动画详解")
st.markdown("""
在 spaCy 的底层算法中，构建依存树就像在玩一个 **“连连看”** 的栈操作游戏。

**核心方向规则解答**：
- **核心词 (Head / 老板)** 永远指向 **修饰词 (Dependent / 小弟)**。
- 以 `the boy` 为例，`boy` 指向 `the`，说明 **`boy` 是核心词，`the` 是修饰它的限定词**。因为 `boy` 在句子中位于 `the` 的**右边**，但它发射出的箭头指向了**左边**的 `the`，所以这个在算法里叫做 **Left-Arc（连向左边）**！
""")

st.markdown("---")

@st.cache_resource(show_spinner=False)
def load_spacy_model(lang="en"):
    model_name = "en_core_web_sm" if lang == "en" else "zh_core_web_sm"
    try:
        return spacy.load(model_name)
    except OSError:
        from spacy.cli import download
        download(model_name)
        return spacy.load(model_name)

if "shared_text" not in st.session_state:
    st.session_state.shared_text = "The boy saw the man with the telescope."
if "shared_lang" not in st.session_state:
    st.session_state.shared_lang = "🇬🇧 英语 (English)"
if "step_idx" not in st.session_state:
    st.session_state.step_idx = 0

def on_animation_text_change():
    st.session_state.shared_text = st.session_state.animation_text_widget
    st.session_state.step_idx = 0

def sync_anim_lang():
    st.session_state.shared_lang = st.session_state.anim_lang_widget
    st.session_state.step_idx = 0

def force_switch_anim_lang(new_lang):
    st.session_state.shared_lang = new_lang
    st.session_state.anim_lang_widget = new_lang
    st.session_state.step_idx = 0

st.markdown("### 🌐 选择解析语言 (Language)")
lang_options = ["🇬🇧 英语 (English)", "🇨🇳 中文 (Chinese)"]

# 【修复状态冲突】
if "anim_lang_widget" not in st.session_state:
    st.session_state.anim_lang_widget = st.session_state.shared_lang
elif st.session_state.anim_lang_widget != st.session_state.shared_lang:
    st.session_state.anim_lang_widget = st.session_state.shared_lang

app_lang = st.radio(
    "模型语言", lang_options, horizontal=True, label_visibility="collapsed",
    key="anim_lang_widget", on_change=sync_anim_lang
)
lang_code = "en" if "English" in app_lang else "zh"

st.markdown("### ✍️ 自定义您的句子 (Input Sentence)")
user_input = st.text_input(
    "输入句子后按回车，下方动画将自动根据您的句子重新生成！", 
    value=st.session_state.shared_text, key="animation_text_widget", on_change=on_animation_text_change
)

nlp = load_spacy_model(lang=lang_code)

current_text = st.session_state.shared_text
has_chinese = any('\u4e00' <= char <= '\u9fa5' for char in current_text)
is_mismatch = False 

if lang_code == "en" and has_chinese:
    st.warning("⚠️ **温馨提示**：您当前使用的是 **🇬🇧 英语模型**，但输入的句子中**包含中文**。这会导致分词错误，导致算法动画完全失效。")
    st.button("👉 一键帮我切换到 🇨🇳 中文模型", key="switch_to_zh_btn_anim", on_click=force_switch_anim_lang, args=("🇨🇳 中文 (Chinese)",))
    is_mismatch = True

elif lang_code == "zh" and not has_chinese and any(c.isalpha() for c in current_text):
    st.warning("⚠️ **温馨提示**：您当前使用的是 **🇨🇳 中文模型**，但输入的句子似乎是**纯英文**。这可能导致分词及依赖判断出现偏差。")
    st.button("👉 一键帮我切换到 🇬🇧 英语模型", key="switch_to_en_btn_anim", on_click=force_switch_anim_lang, args=("🇬🇧 英语 (English)",))
    is_mismatch = True

if not is_mismatch:
    doc = nlp(current_text)
    
    class TokenProxy:
        def __init__(self, text, i, head_i, dep_):
            self.text = text
            self.i = i
            self.head_i = head_i
            self.dep_ = dep_
            self.has_head = False

    tokens = [TokenProxy(t.text, t.i, t.head.i if t.head.i != t.i else -1, t.dep_) for t in doc]
    ROOT = TokenProxy("[ROOT]", -1, -1, "ROOT")
    ROOT.has_head = True

    stack = [ROOT]
    buffer = tokens[:]
    arcs = []

    STEPS = [{
        "action": "🎬 初始状态", "desc": "所有词都在右边缓存区等待，【栈】底永远垫着一个 [ROOT] 节点代表句子的最终主干。",
        "stack": [t.text for t in stack], "buffer": [t.text for t in buffer], "arcs": list(arcs)
    }]

    max_steps = 200 
    step_count = 0
    while len(buffer) > 0 or len(stack) > 1:
        step_count += 1
        if step_count > max_steps:
            break
            
        action_taken = ""
        desc_taken = ""
        
        if len(stack) > 0 and len(buffer) > 0:
            s = stack[-1]
            b = buffer[0]
            
            if s.head_i == b.i and s.i != -1:
                action_taken = "⬅️ Left-Arc (连向左边)"
                desc_taken = f"发现缓存区的 '{b.text}' 是栈顶 '{s.text}' 的老板！连左边箭头，然后消除 {s.text}。"
                arcs.append((b.text, s.text, s.dep_))
                s.has_head = True
                stack.pop()
                
            elif b.head_i == s.i:
                action_taken = "➡️ Right-Arc (连向右边)"
                desc_taken = f"发现栈顶 '{s.text}' 是缓存区 '{b.text}' 的老板！连右边箭头，然后把 {b.text} 移入栈顶（等待其后面的小弟）。"
                arcs.append((s.text, b.text, b.dep_))
                b.has_head = True
                stack.append(buffer.pop(0))
                
            elif s.has_head and not any(t.head_i == s.i for t in buffer):
                action_taken = "🔻 Reduce (规约/消除)"
                desc_taken = f"'{s.text}' 既找到了老板，并且后面等待的词里也没有它的小弟了，清理消除它。"
                stack.pop()
                
            else:
                action_taken = "➡️ Shift (移入栈)"
                desc_taken = f"暂时找不到明确关系，把 '{b.text}' 移入浅灰色栈顶，继续往后看。"
                stack.append(buffer.pop(0))
                
        elif len(buffer) == 0 and len(stack) > 1:
            s = stack.pop()
            action_taken = "🔻 Reduce (规约/消除)"
            desc_taken = f"缓存区已空，收尾清理 '{s.text}'。"
            
        STEPS.append({
            "action": action_taken, "desc": desc_taken,
            "stack": [t.text for t in stack], "buffer": [t.text for t in buffer], "arcs": list(arcs)
        })

    STEPS.append({
        "action": "✅ 解析完成", "desc": "算法贪心决策结束，完美生成依存树（仅限于可投射的常规语序）！",
        "stack": [t.text for t in stack], "buffer": [t.text for t in buffer], "arcs": list(arcs)
    })

    if st.session_state.step_idx >= len(STEPS):
        st.session_state.step_idx = len(STEPS) - 1

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("⏪ 上一步", disabled=(st.session_state.step_idx == 0)):
            st.session_state.step_idx -= 1
            st.rerun()
    with col2:
        if st.button("⏭️ 下一步", type="primary", disabled=(st.session_state.step_idx == len(STEPS)-1)):
            st.session_state.step_idx += 1
            st.rerun()
    with col3:
        if st.button("🔄 重新开始"):
            st.session_state.step_idx = 0
            st.rerun()

    current_step = STEPS[st.session_state.step_idx]

    st.markdown(f"### 当前动作大屏: **<span style='color:#e74c3c'>{current_step['action']}</span>**", unsafe_allow_html=True)
    st.info(current_step['desc'])

    col_stack, col_buffer, col_arcs = st.columns(3)

    with col_stack:
        st.markdown("#### 📚 栈 (Stack)")
        st.markdown("<span style='color:grey; font-size:12px'>已扫过的词（顶层在最上面）</span>", unsafe_allow_html=True)
        if current_step['stack']:
            # 【修复重点】将循环渲染改为先拼接 HTML 字符串，再统一渲染，彻底杜绝前端 removeChild 报错
            stack_html = "".join([f"<div style='background-color:#ffeaa7; padding:10px; margin:5px; border-radius:5px; text-align:center; font-weight:bold; border: 2px solid #fdcb6e; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);'>{word}</div>" for word in reversed(current_step['stack'])])
            st.markdown(stack_html, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:grey; text-align:center; padding:10px;'>(空)</div>", unsafe_allow_html=True)

    with col_buffer:
        st.markdown("#### ⏳ 缓存区 (Buffer)")
        st.markdown("<span style='color:grey; font-size:12px'>还没扫过的词（队首在最上面）</span>", unsafe_allow_html=True)
        if current_step['buffer']:
            # 同理进行字符串拼接
            buffer_html = "".join([f"<div style='background-color:#81ecec; padding:10px; margin:5px; border-radius:5px; text-align:center; font-weight:bold; border: 2px solid #00cec9; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);'>{word}</div>" for word in current_step['buffer']])
            st.markdown(buffer_html, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:grey; text-align:center; padding:10px;'>(空)</div>", unsafe_allow_html=True)

    with col_arcs:
        st.markdown("#### 🌳 建立的依存关系")
        st.markdown("<span style='color:grey; font-size:12px'>老大哥(Head) 支配 小弟(Child)</span>", unsafe_allow_html=True)
        if current_step['arcs']:
            # 同理进行字符串拼接
            arcs_html = "".join([f"<div style='background-color:#a29bfe; color:white; padding:10px; margin:5px; border-radius:5px; text-align:center; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);'><b>{head}</b> ──( {label} )──▶ <b>{dep}</b></div>" for head, dep, label in current_step['arcs']])
            st.markdown(arcs_html, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:grey; text-align:center; padding:10px;'>(暂无连线)</div>", unsafe_allow_html=True)
