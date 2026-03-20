"""
现代自然语言解析器 - Streamlit Web 应用
已添加：全新应用标题
"""

import streamlit as st
import sys
import os

# =======================================================
# === 1. 针对 Python 3.14 & Pydantic V1 的底层兼容性修复 ===
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
# === 2. 针对 benepar & transformers 的深度补丁 ===
# =======================================================
import benepar.retokenization
import benepar.parse_chart

benepar.retokenization.Retokenizer.is_t5 = False
benepar.retokenization.Retokenizer.is_gpt2 = False
benepar.retokenization.Retokenizer.is_xlnet = False
benepar.retokenization.Retokenizer.is_roberta = False

def _patched_retokenizer_init(self, pretrained_model_name_or_path, retain_start_stop=False):
    from transformers import AutoTokenizer
    self.tokenizer = AutoTokenizer.from_pretrained(pretrained_model_name_or_path)
    
    tok_name = type(self.tokenizer).__name__
    self.is_t5 = "T5" in tok_name
    self.is_gpt2 = "GPT2" in tok_name
    self.is_xlnet = "XLNet" in tok_name
    self.is_roberta = "Roberta" in tok_name
    self.retain_start_stop = retain_start_stop
    
    if not hasattr(self.tokenizer, "build_inputs_with_special_tokens"):
        def _manual_build(token_ids_0, token_ids_1=None):
            start_tok = getattr(self.tokenizer, "cls_token_id", getattr(self.tokenizer, "bos_token_id", getattr(self.tokenizer, "start_token_id", None)))
            end_tok = getattr(self.tokenizer, "sep_token_id", getattr(self.tokenizer, "eos_token_id", getattr(self.tokenizer, "end_token_id", None)))
            res = ([start_tok] if start_tok is not None else []) + token_ids_0 + ([end_tok] if end_tok is not None else [])
            return res
        self.tokenizer.build_inputs_with_special_tokens = _manual_build

    try:
        dummy_ids = self.tokenizer.build_inputs_with_special_tokens([-100])
        if self.is_t5 and hasattr(self.tokenizer, "pad_token_id"):
            dummy_ids = [self.tokenizer.pad_token_id] + dummy_ids
        if self.is_gpt2 and hasattr(self.tokenizer, "eos_token_id"):
            dummy_ids = dummy_ids + [self.tokenizer.eos_token_id]
    except Exception:
        dummy_ids = [-100]

    try:
        input_idx = dummy_ids.index(-100)
        self.start_token_idx = (input_idx - 1) if input_idx > 0 else -1
        self.stop_token_idx = -(len(dummy_ids) - input_idx - 1) if (len(dummy_ids) - input_idx - 1) > 0 else 0
    except ValueError:
        self.start_token_idx = -1
        self.stop_token_idx = 0

benepar.retokenization.Retokenizer.__init__ = _patched_retokenizer_init

if not hasattr(benepar.parse_chart.ChartParser, "_orig_load_state_dict"):
    benepar.parse_chart.ChartParser._orig_load_state_dict = benepar.parse_chart.ChartParser.load_state_dict
    def _patched_load_state_dict(self, state_dict, strict=True, **kwargs):
        filtered_state_dict = {k: v for k, v in state_dict.items() if "position_ids" not in k}
        return benepar.parse_chart.ChartParser._orig_load_state_dict(self, filtered_state_dict, strict=False, **kwargs)
    benepar.parse_chart.ChartParser.load_state_dict = _patched_load_state_dict

# =======================================================
# === 3. 页面业务逻辑与 UI 渲染 ===
# =======================================================
import spacy
import nltk
import svgling
import warnings
warnings.filterwarnings('ignore')

# 将网页的 Title 也改了，让浏览器标签页也显得高大上
st.set_page_config(page_title="句法双引擎透视仪", page_icon="🕵️‍♂️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main-title { font-family: 'Helvetica Neue', Arial, sans-serif; font-weight: 700; color: #2c3e50; text-align: center; margin-bottom: 0.5rem; margin-top: 1rem; }
    div.row-widget.stRadio > div { background-color: #f1f3f6; padding: 10px; border-radius: 12px; display: flex; justify-content: center; margin-bottom: 10px; }
    div.row-widget.stRadio > div > label > div:first-child { display: none; }
    div.row-widget.stRadio > div > label { padding: 8px 24px; background-color: white; border-radius: 6px; margin: 0 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# 🚀 【新增】炫酷的应用主标题
st.markdown("<h1 class='main-title'>🕵️‍♂️ 句法双引擎透视仪与“歧义侦探”</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #7f8c8d; margin-bottom: 2rem;'>深度解析语言结构，一键看透句子背后的逻辑骨架</p>", unsafe_allow_html=True)
st.markdown("---")

@st.cache_resource(show_spinner=False)
def load_models(lang="en"):
    import benepar
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
        
    spacy_model = "en_core_web_sm" if lang == "en" else "zh_core_web_sm"
    benepar_model = "benepar_en3" if lang == "en" else "benepar_zh2"
        
    try:
        benepar.download(benepar_model)
    except Exception:
        pass

    try:
        nlp = spacy.load(spacy_model)
    except OSError:
        from spacy.cli import download as spacy_download
        spacy_download(spacy_model)
        nlp = spacy.load(spacy_model)
        
    if "benepar" not in nlp.pipe_names:
        nlp.add_pipe("benepar", config={"model": benepar_model})
    return nlp

if "shared_text" not in st.session_state:
    st.session_state.shared_text = "The boy saw the man with the telescope."
if "shared_lang" not in st.session_state:
    st.session_state.shared_lang = "🇬🇧 英语 (English)"

def sync_app_text():
    st.session_state.shared_text = st.session_state.app_text_widget

def sync_app_lang():
    st.session_state.shared_lang = st.session_state.app_lang_widget

def force_switch_app_lang(new_lang):
    st.session_state.shared_lang = new_lang
    st.session_state.app_lang_widget = new_lang

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

st.markdown("### ✍️ 输入需要分析的句子")
text = st.text_input(
    "您可以修改下方文本进行自定义解析：", value=st.session_state.shared_text, 
    max_chars=200, key="app_text_widget", on_change=sync_app_text
)

if text.strip():
    st.markdown("---")
    display_mode = st.radio(
        "选择解析模式 👇", ["🔗 依存句法分析 (Dependency Parsing)", "🌿 成分句法分析 (Constituency Parsing)"], 
        horizontal=True, label_visibility="collapsed", key="app_display_mode_widget"
    )
    st.markdown("<br>", unsafe_allow_html=True)
    
    has_chinese = any('\u4e00' <= char <= '\u9fa5' for char in text)
    is_mismatch = False
    
    if lang_code == "en" and has_chinese:
        st.warning("⚠️ **温馨提示**：您当前使用的是 **🇬🇧 英语模型**，但输入的句子中**包含中文**。为了防止深度结构解析模型运算时引发崩溃乱码，系统已为您拦截本次渲染。")
        st.button("👉 一键帮我切换到 🇨🇳 中文模型", key="switch_to_zh_btn", on_click=force_switch_app_lang, args=("🇨🇳 中文 (Chinese)",))
        is_mismatch = True
        
    elif lang_code == "zh" and not has_chinese and any(c.isalpha() for c in text):
        st.warning("⚠️ **温馨提示**：您当前使用的是 **🇨🇳 中文模型**，但输入的句子似乎是**纯英文**。为了防止底层汉字库解析英文时发生运算越界导致错误，系统已为您拦截。")
        st.button("👉 一键帮我切换到 🇬🇧 英语模型", key="switch_to_en_btn", on_click=force_switch_app_lang, args=("🇬🇧 英语 (English)",))
        is_mismatch = True
    
    if not is_mismatch:
        with st.spinner(f"正在加载 {app_lang} 模型并进行深度句法解析，请耐心稍候..."):
            nlp = load_models(lang=lang_code)
            doc = nlp(text)
        
        sents = list(doc.sents)
        
        if display_mode == "🔗 依存句法分析 (Dependency Parsing)":
            st.markdown("<div style='font-weight:bold; font-size:1.2em; margin-bottom:10px;'>依存句法分析 (Dependency Parsing)</div>", unsafe_allow_html=True)
            st.info("展示词汇之间的修饰与支配关系（由 spaCy 提供支持）")
            
            if len(sents) > 1:
                dep_tabs = st.tabs([f"🔷 句子 {idx+1}" for idx in range(len(sents))])
                for idx, (sent, tab) in enumerate(zip(sents, dep_tabs)):
                    with tab:
                        st.markdown(f"**▶️ 原文:** `{sent.text}`")
                        svg_dep = spacy.displacy.render(sent, style="dep", jupyter=False)
                        st.markdown(f"<div style='overflow-x: auto; margin-top: 15px; margin-bottom: 20px; text-align: center;'>{svg_dep}</div>", unsafe_allow_html=True)
            elif len(sents) == 1:
                svg_dep = spacy.displacy.render(doc, style="dep", jupyter=False)
                st.markdown(f"<div style='overflow-x: auto; margin-top: 15px; margin-bottom: 20px; text-align: center;'>{svg_dep}</div>", unsafe_allow_html=True)
            else:
                st.warning("未能提取到有效句子。")

        elif display_mode == "🌿 成分句法分析 (Constituency Parsing)":
            st.markdown("<div style='font-weight:bold; font-size:1.2em; margin-bottom:10px;'>成分句法分析 (Constituency Parsing)</div>", unsafe_allow_html=True)
            st.info("展示句子中短语如同树枝般的嵌套结构（由 Berkeley Neural Parser 提供支持）")
            
            if sents:
                try:
                    from spacy.tokens import Span
                    from nltk.tree import ParentedTree
                    if not Span.has_extension("parse_string"):
                        Span.set_extension("parse_string", default="")
                    if not Span.has_extension("labels"):
                        Span.set_extension("labels", default=tuple())
                    if not Span.has_extension("tree"):
                        Span.set_extension("tree", getter=lambda span: ParentedTree.fromstring(span._.parse_string) if span._.parse_string else None)

                    if len(sents) > 1:
                        const_tabs = st.tabs([f"🔷 句子 {idx+1}" for idx in range(len(sents))])
                        iterator = enumerate(zip(sents, const_tabs))
                    elif len(sents) == 1:
                        const_tabs = [st.container()]
                        iterator = enumerate(zip(sents, const_tabs))
                    else:
                        iterator = []

                    for idx, (sent, tab) in iterator:
                        with tab:
                            if len(sents) > 1:
                                st.markdown(f"**▶️ 原文:** `{sent.text}`")
                                
                            tree = sent._.tree
                            if tree:
                                if lang_code == "zh":
                                    tree_opts = svgling.core.TreeOptions(average_glyph_width=1.0, leaf_padding=1.5, distance_to_daughter=3)
                                    svg_const = svgling.draw_tree(tree, options=tree_opts)._repr_svg_()
                                else:
                                    svg_const = svgling.draw_tree(tree)._repr_svg_()
                                
                                st.markdown(f"<div style='display:flex; justify-content:center; overflow-x: auto; margin-bottom: 5px;'>{svg_const}</div>", unsafe_allow_html=True)
                                with st.expander("查看纯文本树状结构 (Text Tree)", expanded=(idx == 0)):
                                    st.markdown(f"<div style='font-family: monospace; white-space: pre-wrap; word-break: break-word; background-color: #f8f9fa; padding: 15px; border-radius: 8px; color: #2c3e50;'>{sent._.parse_string}</div>", unsafe_allow_html=True)
                            else:
                                st.warning("该句子未能生成完整的成分树。")
                except Exception as e:
                    st.error(f"解析成分句法树时发生错误：{str(e)}\n\n(提示: 请确保输入的是英文整句，或者可能遇到未预料的语法错误)")
            else:
                st.warning("未能提取到有效句子的成分结构。")

        st.markdown("---")
        st.markdown("### 🔍 核心论元提取器 (Core Argument Extractor)")
        st.info("基于依存句法理论，自动为您提取句子中最核心的关键角色：主谓宾。")
        
        target_deps = {"ROOT", "nsubj", "dobj", "pobj"}
        arguments = []
        dep_descriptions = {"ROOT": "根谓语 (全句核心动作)", "nsubj": "名义主语 (动作执行者)", "dobj": "直接宾语 (动作承受者)", "pobj": "介词宾语 (介词连带词)"}

        if sents:
            for idx, sent in enumerate(sents):
                for token in sent:
                    if token.dep_ in target_deps:
                        arguments.append({
                            "所属句子": f"句子 {idx+1}", "提取词 (Token)": token.text,
                            "词根 (Lemma)": token.lemma_, "词性 (POS)": token.pos_,
                            "支配词老板 (Head)": token.head.text, "依存标签 (Dep)": token.dep_,
                            "论元角色推理": dep_descriptions.get(token.dep_, token.dep_)
                        })
                        
            if arguments:
                st.dataframe(arguments, use_container_width=True, hide_index=True)
            else:
                st.warning("并未提取到相关的核心论元结构。")
else:
    st.warning("⚠️ 请输入有效的句子以进行解析。")
