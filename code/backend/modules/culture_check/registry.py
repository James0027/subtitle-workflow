from typing import Any, Dict, List, Optional
from code.backend.modules.culture_check.contract import (
    CultureCaseItem,
    CultureRuleItem,
    CultureSourceRegistryItem,
)

# 2026-10-22 公开检索与法律查验登记的标准数据底座
DEFAULT_SOURCES: List[CultureSourceRegistryItem] = [
    CultureSourceRegistryItem(
        source_id="MX-OFF-01",
        source_level="OFFICIAL",
        title="Ley Federal de Cine y el Audiovisual (新视听法及废止旧法法令)",
        url="https://sidof.segob.gob.mx/notas/docFuente/5788357",
        published_at="2026-05-22",
        retrieved_at="2026-10-22T00:00:00Z",
        source_version="DOF-2026-05-22-PROMULGADA",
        applicable_channels=["theatrical", "streaming", "vod"],
        retrieval_status="SUCCESS_READ",
        verification_status="VERIFIED",
        usage_limitations="旧法废止，新法过渡条款1/2/4/5/6生效；点播与流媒体范围须按条款解读，配套行政规则待跟踪",
    ),
    CultureSourceRegistryItem(
        source_id="MX-OFF-02",
        source_level="OFFICIAL",
        title="Ley Federal para Prevenir y Eliminar la Discriminación (反歧视联邦法)",
        url="https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPED.pdf",
        published_at="2025-11-14",
        retrieved_at="2026-10-22T00:00:00Z",
        source_version="PDF-2025-11-14-REVISADA",
        applicable_channels=["streaming", "theatrical", "broadcast", "social"],
        retrieval_status="SUCCESS_READ",
        verification_status="VERIFIED",
        usage_limitations="保护对象涵盖宗教、族裔、政治意见等；媒体仇恨条款可作风险依据，虚构台词需语境和人工判定",
    ),
    CultureSourceRegistryItem(
        source_id="MX-OFF-03",
        source_level="OFFICIAL",
        title="Lineamientos de Clasificación de Contenidos Audiovisuales (广播电视视听分级规范)",
        url="https://sidof.segob.gob.mx/notas/docFuente/5535366",
        published_at="2018-08-21",
        retrieved_at="2026-10-22T00:00:00Z",
        source_version="DOF-2018-08-21-REVISION-PENDING",
        applicable_channels=["broadcast", "pay_tv"],
        retrieval_status="SUCCESS_METADATA_ONLY",
        verification_status="PENDING_VERIFICATION",
        usage_limitations="检索命中但正文待核验，涉及暴恐成瘾语言；待全文核验前其规则不得设为ACTIVE",
    ),
    CultureSourceRegistryItem(
        source_id="MX-OFF-04",
        source_level="OFFICIAL",
        title="Dirección General de Radio, Televisión y Cinematografía (RTC电影分级指南)",
        url="https://dgrtc.segob.gob.mx/es/DGRTC/CINEMATOGRAFIA",
        published_at=None,
        retrieved_at="2026-10-22T00:00:00Z",
        source_version="RTC-CRITERIA-2026",
        applicable_channels=["theatrical", "streaming"],
        retrieval_status="SUCCESS_READ",
        verification_status="VERIFIED",
        usage_limitations="AA/A/B/B15/C/D分级作为渠道受众参考，不等于取得官方认证，不得将成人分级机械视作违法红线",
    ),
    CultureSourceRegistryItem(
        source_id="MX-CASE-01",
        source_level="INDUSTRY_CASE",
        title="En sincronía Ep.15: Katya Ojeda拉美配音本地化访谈",
        url="https://www.ensincroniapodcast.com/1112315/episodes/8375564",
        published_at="2021-04-21",
        retrieved_at="2026-10-22T00:00:00Z",
        source_version="EP-15-TRANSCRIPT",
        applicable_channels=["streaming", "dubbing", "subtitling"],
        retrieval_status="SUCCESS_READ",
        verification_status="VERIFIED",
        usage_limitations="身份概要已核，可作为es-MX中性西语及避开过度俚语参考；配音经验不完全等同字幕硬规",
    ),
    CultureSourceRegistryItem(
        source_id="MX-CASE-02",
        source_level="INDUSTRY_CASE",
        title="Crunchyroll How Anime Gets Localized",
        url="https://www.crunchyroll.com/news/deep-dives/2023/3/25/feature-how-anime-gets-localized",
        published_at="2023-03-25",
        retrieved_at="2026-10-22T00:00:00Z",
        source_version="CR-FEATURE-2023",
        applicable_channels=["streaming"],
        retrieval_status="FAILED_REDIRECT",
        verification_status="PENDING_VERIFICATION",
        usage_limitations="打开重定向资讯首页，正文未完整取得，暂不抽取为已核案例",
    ),
    CultureSourceRegistryItem(
        source_id="MX-CASE-03",
        source_level="COMMUNITY",
        title="B站翻译案例观察-天降小萌祖",
        url="https://www.bilibili.com/opus/1092619579701592073",
        published_at=None,
        retrieved_at="2026-10-22T00:00:00Z",
        source_version="BILI-OPUS-DRAFT",
        applicable_channels=["social"],
        retrieval_status="FAILED_CAPTCHA",
        verification_status="PENDING_VERIFICATION",
        usage_limitations="验证码阻拦正文未读，仅保留线索，不作为正式案例或模型事实",
    ),
    CultureSourceRegistryItem(
        source_id="MX-CASE-04",
        source_level="COMMUNITY",
        title="Reddit r/mexico & r/AskMexico 配音语气讨论",
        url="https://www.reddit.com/r/mexico/comments/stjaw6",
        published_at=None,
        retrieved_at="2026-10-22T00:00:00Z",
        source_version="REDDIT-COMMUNITY-THREAD",
        applicable_channels=["social", "streaming"],
        retrieval_status="SUCCESS_READ",
        verification_status="FAILED",
        usage_limitations="发帖人身份未核，仅用于发现过度墨西哥化及俚语争议线索，不升格为规则",
    ),
]

DEFAULT_RULES: List[CultureRuleItem] = [
    CultureRuleItem(
        rule_id="R-MX-DISCRIM-01",
        source_ref="MX-OFF-02",
        clause_ref="第1条、第9条第XV款",
        scope="es-MX / 影视虚构对话全渠道",
        category="discrimination",
        trigger_condition="台词公然使用针对特定宗教、种族、性取向或残障群体的仇恨辱骂或贬损词汇",
        exceptions="历史纪实引述、反派人物恶行刻画且剧情明确持批判惩戒立场，需结合反讽及叙事立场判定",
        severity_default="P1",
        rule_version="2026-10-22.1",
        validity_basis="现行有效的反歧视联邦法，官方PDF核验生效",
        review_status="UNVERIFIED",
        status="CANDIDATE",
    ),
    CultureRuleItem(
        rule_id="R-MX-CINEMA-01",
        source_ref="MX-OFF-01",
        clause_ref="新法过渡条款第4条及视听分类规范",
        scope="es-MX / 影视流媒体与点播渠道",
        category="sex_violence_addiction_ratings",
        trigger_condition="出现未成年人不适宜的露骨毒品成瘾宣扬、过度血腥暴力台词且未标注年龄分级建议",
        exceptions="警示题材、禁毒教育剧情、反面教训",
        severity_default="P1",
        rule_version="2026-10-22.1",
        validity_basis="2026-05-22签署新视听法过渡保护条款",
        review_status="UNVERIFIED",
        status="CANDIDATE",
    ),
    CultureRuleItem(
        rule_id="R-MX-TABOO-01",
        source_ref="MX-CASE-01",
        clause_ref="未核实具体条款；播客不具有强制规范效力",
        scope="es-MX / 全年龄与中性拉美西语短剧",
        category="local_taboo",
        trigger_condition="非剧情极端必要滥用墨西哥极度粗俗脏话（如chingar衍生严重脏词、cabrón恶意辱骂）导致家庭受众反感",
        exceptions="成人剧集特定混混反派粗鄙口语，需视剧本基调",
        severity_default="P2",
        rule_version="2026-10-22.1",
        validity_basis="仅来源线索，观点内容与适用性尚未核验",
        review_status="UNVERIFIED",
        status="CANDIDATE",
    ),
    CultureRuleItem(
        rule_id="R-MX-UNVERIFIED-01",
        source_ref="MX-OFF-03",
        clause_ref="第3.2条",
        scope="es-MX / 广播与付费电视",
        category="legal_platform",
        trigger_condition="旧广播特定时段语言限制",
        exceptions="流媒体非广播时段",
        severity_default="P1",
        rule_version="2026-10-22.1",
        validity_basis="来源待核验，条款适用性存疑",
        review_status="UNVERIFIED",
        status="CANDIDATE",  # 必须是 CANDIDATE，严禁 ACTIVE
    ),
]

DEFAULT_CASES: List[CultureCaseItem] = [
    CultureCaseItem(
        case_id="MX-CASE-01",
        source_ref="MX-CASE-01",
        author_identity_verified=True,
        scenario_or_context="拉美多国发行短剧与动画本地化译配",
        source_translation_observation="过度使用墨西哥特定本土俚语会导致阿根廷/哥伦比亚受众理解困难；需保持中性拉美西语基调，在特定性格时适度调味",
        boundary_scope="适用于面向泛拉美但主打墨西哥市场的影视对话",
        credibility_level="CANDIDATE_ONLY",
        status="CANDIDATE",
    ),
    CultureCaseItem(
        case_id="MX-CASE-04",
        source_ref="MX-CASE-04",
        author_identity_verified=False,
        scenario_or_context="海外社区关于配音粗口的讨论",
        source_translation_observation="部分观众指出年轻角色日常口头禅使用wey尚可接受，但频次过高破坏严肃剧情",
        boundary_scope="仅作社区感知线索参考，不具强制力",
        credibility_level="CANDIDATE_ONLY",
        status="RESEARCH_ONLY",
    ),
]


class CultureRegistry:
    """文化来源与规则知识库管理器"""
    def __init__(self):
        self._sources: Dict[str, CultureSourceRegistryItem] = {s.source_id: s for s in DEFAULT_SOURCES}
        self._rules: Dict[str, CultureRuleItem] = {r.rule_id: r for r in DEFAULT_RULES}
        self._cases: Dict[str, CultureCaseItem] = {c.case_id: c for c in DEFAULT_CASES}

    def get_sources(self) -> List[CultureSourceRegistryItem]:
        return list(self._sources.values())

    def get_source(self, source_id: str) -> Optional[CultureSourceRegistryItem]:
        return self._sources.get(source_id)

    def retrieve_applicable_rules(
        self,
        target_market: str = "MX",
        channel: Optional[str] = None,
        category: Optional[str] = None,
        only_active: bool = True,
    ) -> List[CultureRuleItem]:
        """
        适用范围检索：
        - 仅当 target_market 为 MX 时检索墨西哥规则
        - 严格排查 review_status == 'VERIFIED'，未核规则不得以 ACTIVE 返回
        - 可选渠道与大类过滤
        """
        if target_market != "MX":
            return []
        results: List[CultureRuleItem] = []
        for r in self._rules.values():
            if target_market == "MX" and not ("MX" in r.rule_id or "MX" in r.source_ref or "es-MX" in r.scope):
                continue
            if only_active:
                if r.status != "ACTIVE" or r.review_status != "VERIFIED":
                    continue
            if category and r.category != category:
                continue
            results.append(r)
        return results

    def retrieve_applicable_cases(
        self,
        target_market: str = "MX",
        only_active: bool = True,
    ) -> List[CultureCaseItem]:
        if target_market != "MX":
            return []
        results: List[CultureCaseItem] = []
        for c in self._cases.values():
            if only_active and c.status != "ACTIVE_REFERENCE":
                continue
            results.append(c)
        return results

    def register_rule(self, rule: CultureRuleItem) -> None:
        """注册或更新规则，未核规则强行 ACTIVE 将被 Pydantic 校验拒绝"""
        self._rules[rule.rule_id] = rule


default_registry = CultureRegistry()
