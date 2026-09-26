<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>

    <header class="page-head">
      <div>
        <h2>技术评定等级一览</h2>
        <p class="page-desc">与技术评定列表、详情页同源，确认定级或复评后这里同步刷新。</p>
      </div>
    </header>
    <table class="data-table">
      <thead>
        <tr><th>评定编号</th><th>评定对象</th><th>技术等级</th><th>评定状态</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in assessGrades" :key="String(row.id)">
          <td>{{ row['评定编号'] }}</td>
          <td>{{ row['评定对象'] }}</td>
          <td>{{ row['技术等级'] }}</td>
          <td>{{ row['评定状态'] }}</td>
        </tr>
        <tr v-if="!assessGrades.length">
          <td colspan="4" class="empty-state">暂无技术评定等级数据</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
  assess_grades: { id: number; 评定编号: string; 评定对象: string; 技术等级: string; 评定状态: string }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const assessGrades = ref<Overview['assess_grades']>([])

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
    assessGrades.value = payload.assess_grades ?? []
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "道路设施", "created": 0, "pending": 0, "abnormal": 0}, {"name": "桥梁档案", "created": 0, "pending": 0, "abnormal": 0}, {"name": "隧道设施", "created": 0, "pending": 0, "abnormal": 0}, {"name": "巡查任务", "created": 0, "pending": 0, "abnormal": 0}, {"name": "病害登记", "created": 0, "pending": 0, "abnormal": 0}, {"name": "技术评定", "created": 0, "pending": 0, "abnormal": 0}, {"name": "养护计划", "created": 0, "pending": 0, "abnormal": 0}, {"name": "养护施工", "created": 0, "pending": 0, "abnormal": 0}, {"name": "竣工验收", "created": 0, "pending": 0, "abnormal": 0}, {"name": "坑槽修补", "created": 0, "pending": 0, "abnormal": 0}, {"name": "裂缝处置", "created": 0, "pending": 0, "abnormal": 0}, {"name": "排水设施", "created": 0, "pending": 0, "abnormal": 0}, {"name": "照明设施", "created": 0, "pending": 0, "abnormal": 0}, {"name": "养护材料", "created": 0, "pending": 0, "abnormal": 0}, {"name": "养护机械", "created": 0, "pending": 0, "abnormal": 0}, {"name": "养护资金", "created": 0, "pending": 0, "abnormal": 0}, {"name": "公众诉求", "created": 0, "pending": 0, "abnormal": 0}, {"name": "设施档案", "created": 0, "pending": 0, "abnormal": 0}]
  }
})
</script>
