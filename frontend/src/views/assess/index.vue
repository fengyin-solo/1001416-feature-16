<template>
  <section class="page" data-module="assess">
    <header class="page-head">
      <div>
        <h2>技术评定管理</h2>
        <p class="page-desc">维护评定记录，围绕评定编号、评定对象、评定周期、技术等级做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记评定记录</button>
        <button class="btn" type="button" @click="exportRows">导出技术评定清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] || '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in allowedActions(String(row['评定状态'] ?? row.status ?? ''))"
              :key="action"
              class="link"
              type="button"
              @click="onRowAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无技术评定数据，可先登记评定记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条技术评定记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detail" class="drawer-mask" @click.self="closeDetail">
      <aside class="drawer">
        <header class="drawer-head">
          <h3>评定详情 · {{ detail['评定编号'] }}</h3>
          <button class="link" type="button" @click="closeDetail">关闭</button>
        </header>

        <dl class="detail-grid">
          <div v-for="column in columns" :key="column" class="detail-item">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] || '—' }}</dd>
          </div>
        </dl>

        <form class="grade-form" @submit.prevent>
          <h4>本次结论</h4>
          <label class="filter-item">
            <span>技术等级</span>
            <input v-model="gradeForm.技术等级" placeholder="如：一类 / 二类 / 三类" />
          </label>
          <label class="filter-item">
            <span>评定结论</span>
            <textarea v-model="gradeForm.评定结论" rows="3" placeholder="填写本次评定结论"></textarea>
          </label>
          <label class="filter-item">
            <span>评定人员</span>
            <input v-model="gradeForm.评定人员" placeholder="填写评定人员" />
          </label>
          <div class="drawer-actions">
            <button
              v-for="action in allowedActions(String(detail['评定状态'] ?? ''))"
              :key="action"
              class="btn primary"
              type="button"
              @click="runAction(action, detail)"
            >
              {{ action }}
            </button>
            <span v-if="!allowedActions(String(detail['评定状态'] ?? '')).length" class="muted-text">
              已复评的记录不能回退，仅可查看
            </span>
          </div>
          <p v-if="detailMessage" :class="detailMessageOk ? 'ok-text' : 'error-text'">{{ detailMessage }}</p>
        </form>

        <section class="history-block">
          <h4>历史结论（只读，不会被新提交覆盖）</h4>
          <table class="data-table">
            <thead>
              <tr><th>记录时间</th><th>动作</th><th>技术等级</th><th>评定结论</th><th>评定人员</th></tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in detailHistory" :key="index">
                <td>{{ item['记录时间'] || '—' }}</td>
                <td>{{ item['动作'] || '—' }}</td>
                <td>{{ item['技术等级'] || '—' }}</td>
                <td>{{ item['评定结论'] || '—' }}</td>
                <td>{{ item['评定人员'] || '—' }}</td>
              </tr>
              <tr v-if="!detailHistory.length">
                <td colspan="5" class="empty-state">暂无历史结论</td>
              </tr>
            </tbody>
          </table>
        </section>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type HistoryItem = Record<string, string | number | null>

const ENDPOINT = '/api/assess'
const columns = ["评定编号", "评定对象", "评定周期", "技术等级", "评定结论", "评定人员", "评定日期", "评定状态"]
const statuses = ["待评定", "评定中", "已定级", "已复评"]
// 与后端 ACTION_FLOW 保持一致：状态只能向前走，已复评不能回退到评定中
const ACTION_FLOW: Record<string, string[]> = {
  "开始评定": ["待评定"],
  "确认定级": ["评定中", "已定级"],
  "发起复评": ["已定级", "已复评"],
}
const NEEDS_CONCLUSION = new Set(["确认定级", "发起复评"])
const stats = [{"label": "待评定对象", "value": 0}, {"label": "低等级设施", "value": 0}, {"label": "本月评定数", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const detail = ref<Row | null>(null)
const detailMessage = ref('')
const detailMessageOk = ref(false)
const gradeForm = ref({ "技术等级": '', "评定结论": '', "评定人员": '' })

const detailHistory = computed<HistoryItem[]>(() => {
  const history = detail.value?.history
  return Array.isArray(history) ? (history as HistoryItem[]) : []
})

function allowedActions(status: string): string[] {
  return Object.entries(ACTION_FLOW)
    .filter(([, sources]) => sources.includes(status))
    .map(([action]) => action)
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '评定记录登记入口尚未接入审批流'
}

async function openDetail(row: Row) {
  detailMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('评定详情读取失败')
    }
    detail.value = await response.json()
    gradeForm.value = {
      "技术等级": String(detail.value?.["技术等级"] ?? ''),
      "评定结论": '',
      "评定人员": String(detail.value?.["评定人员"] ?? ''),
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '评定详情读取失败'
  }
}

function closeDetail() {
  detail.value = null
  detailMessage.value = ''
}

function onRowAction(action: string, row: Row) {
  // 定级与复评需要填写结论，先打开详情抽屉；开始评定无需结论可直接执行
  if (NEEDS_CONCLUSION.has(action)) {
    void openDetail(row)
    return
  }
  void runAction(action, row)
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  detailMessage.value = ''
  detailMessageOk.value = false
  const values: Record<string, string> = { action }
  if (NEEDS_CONCLUSION.has(action)) {
    const missing: string[] = []
    if (!gradeForm.value["技术等级"].trim()) missing.push('技术等级')
    if (!gradeForm.value["评定结论"].trim()) missing.push('评定结论')
    if (missing.length) {
      detailMessage.value = `以下项目不合规：${missing.join('、')}为空；本次提交未生效，仍保留原技术等级「${row["技术等级"] || '未评定'}」`
      return
    }
    values["技术等级"] = gradeForm.value["技术等级"].trim()
    values["评定结论"] = gradeForm.value["评定结论"].trim()
    values["评定人员"] = gradeForm.value["评定人员"].trim()
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '技术评定动作未生效，请稍后重试')
    }
    if (detail.value && payload.entry) {
      detail.value = payload.entry
    }
    if (payload.message) {
      detailMessageOk.value = true
      detailMessage.value = payload.message
    }
    await reload()
  } catch (error) {
    const message = error instanceof Error ? error.message : '技术评定操作失败'
    if (detail.value) {
      detailMessage.value = message
    } else {
      errorMessage.value = message
    }
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('评定记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '技术评定列表读取失败'
  }
}

onMounted(reload)
</script>
