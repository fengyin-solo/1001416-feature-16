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
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">结论与定级</button>
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

    <div v-if="detail" class="panel-mask" @click.self="closeDetail">
      <div class="panel">
        <header class="panel-head">
          <h3 class="panel-title">评定详情 · {{ detail['评定编号'] ?? '' }}</h3>
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </header>
        <p class="panel-meta">
          <span>评定对象：{{ detail['评定对象'] ?? '—' }}</span>
          <span>评定周期：{{ detail['评定周期'] ?? '—' }}</span>
          <span>当前状态：{{ detail.status ?? '—' }}</span>
        </p>

        <div class="form-grid">
          <label class="form-item">
            <span>技术等级</span>
            <select v-model="form.技术等级">
              <option value="" disabled>请选择技术等级</option>
              <option v-for="grade in gradeOptions" :key="grade" :value="grade">{{ grade }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>评定人员</span>
            <input v-model="form.评定人员" placeholder="填写评定人员" />
          </label>
          <label class="form-item">
            <span>评定日期</span>
            <input v-model="form.评定日期" type="date" />
          </label>
          <label class="form-item full">
            <span>评定结论</span>
            <textarea v-model="form.评定结论" rows="3" placeholder="填写本次评定结论，确认定级或发起复评时必填"></textarea>
          </label>
        </div>

        <div class="panel-actions">
          <button
            v-for="action in actions"
            :key="action"
            class="btn primary"
            type="button"
            :disabled="submitting || !canRun(action)"
            @click="submitAction(action)"
          >
            {{ action }}
          </button>
          <span v-if="isFinal" class="panel-hint">已复评为最终状态，不能再回退到评定中</span>
        </div>
        <p v-if="panelMessage" class="panel-message" :class="panelOk ? 'ok' : 'fail'">{{ panelMessage }}</p>

        <h4 class="history-title">历史评定结论</h4>
        <table class="data-table">
          <thead>
            <tr><th>记录时间</th><th>动作</th><th>技术等级</th><th>评定结论</th><th>评定人员</th></tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in historyRows" :key="index">
              <td>{{ item['记录时间'] || '—' }}</td>
              <td>{{ item['动作'] || '—' }}</td>
              <td>{{ item['技术等级'] || '—' }}</td>
              <td>{{ item['评定结论'] || '—' }}</td>
              <td>{{ item['评定人员'] || '—' }}</td>
            </tr>
            <tr v-if="!historyRows.length">
              <td colspan="5" class="empty-state">暂无历史结论</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type HistoryEntry = {
  动作?: string
  技术等级?: string
  评定结论?: string
  评定人员?: string
  评定日期?: string
  记录时间?: string
}

type Row = {
  id?: number | string
  status?: string
  history?: HistoryEntry[]
  [key: string]: unknown
}

type ActionPayload = {
  ok: boolean
  message: string
  entry?: Row | null
}

const ENDPOINT = '/api/assess'
const columns = ["评定编号", "评定对象", "评定周期", "技术等级", "评定结论", "评定人员", "评定日期", "评定状态"]
const actions = ["开始评定", "确认定级", "发起复评"]
const STATUS_ORDER = ["待评定", "评定中", "已定级", "已复评"]
const ACTION_TARGET: Record<string, string> = { 开始评定: "评定中", 确认定级: "已定级", 发起复评: "已复评" }
const GRADE_OPTIONS = ["一类", "二类", "三类", "四类", "五类"]
const stats = [{"label": "待评定对象", "value": 0}, {"label": "低等级设施", "value": 0}, {"label": "本月评定数", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const detail = ref<Row | null>(null)
const historyRows = ref<HistoryEntry[]>([])
const form = ref({ 技术等级: '', 评定结论: '', 评定人员: '', 评定日期: '' })
const submitting = ref(false)
const panelMessage = ref('')
const panelOk = ref(false)

const gradeOptions = computed(() => {
  const current = form.value.技术等级
  return current && !GRADE_OPTIONS.includes(current) ? [current, ...GRADE_OPTIONS] : GRADE_OPTIONS
})

const isFinal = computed(() => detail.value?.status === STATUS_ORDER[STATUS_ORDER.length - 1])

function statusIndex(status: unknown) {
  const index = STATUS_ORDER.indexOf(String(status ?? ''))
  return index === -1 ? 0 : index
}

function canRun(action: string) {
  if (!detail.value) {
    return false
  }
  return statusIndex(ACTION_TARGET[action]) >= statusIndex(detail.value.status)
}

function asText(value: unknown) {
  return value === null || value === undefined ? '' : String(value)
}

function applyDetail(entry: Row) {
  detail.value = entry
  const history = Array.isArray(entry.history) ? entry.history : []
  historyRows.value = [...history].reverse()
  form.value = {
    技术等级: asText(entry['技术等级']),
    评定结论: asText(entry['评定结论']),
    评定人员: asText(entry['评定人员']),
    评定日期: asText(entry['评定日期']),
  }
}

async function openDetail(row: Row) {
  panelMessage.value = ''
  panelOk.value = false
  try {
    const payload = await fetchJson<Row>(`${ENDPOINT}/${row.id}`)
    applyDetail(payload)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '评定详情读取失败'
  }
}

function closeDetail() {
  detail.value = null
  panelMessage.value = ''
  panelOk.value = false
}

async function submitAction(action: string) {
  if (!detail.value || submitting.value) {
    return
  }
  submitting.value = true
  panelMessage.value = ''
  panelOk.value = false
  try {
    const response = await request(`${ENDPOINT}/${detail.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action, ...form.value }),
    })
    const payload = (await response.json()) as ActionPayload
    if (!response.ok || !payload.ok) {
      panelMessage.value = payload?.message || '技术评定动作未生效，请稍后重试'
      return
    }
    panelOk.value = true
    panelMessage.value = payload.message
    if (payload.entry) {
      applyDetail(payload.entry)
    }
    await reload()
  } catch (error) {
    panelMessage.value = error instanceof Error ? error.message : '技术评定操作失败'
  } finally {
    submitting.value = false
  }
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

<style scoped>
.panel-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 40px 16px;
  z-index: 10;
}
.panel {
  background: #fff;
  border-radius: 10px;
  width: 640px;
  max-width: 100%;
  max-height: calc(100vh - 80px);
  overflow: auto;
  padding: 16px 20px;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-title {
  margin: 0;
  font-size: 16px;
}
.panel-meta {
  color: var(--muted);
  font-size: 13px;
  margin: 8px 0 12px;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 14px;
  margin-bottom: 12px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-item input,
.form-item select,
.form-item textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  font-family: inherit;
}
.form-item.full {
  grid-column: 1 / -1;
}
.panel-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.panel-hint {
  font-size: 12px;
  color: var(--muted);
}
.panel-message {
  font-size: 13px;
  margin: 0 0 12px;
}
.panel-message.ok {
  color: #067647;
}
.panel-message.fail {
  color: #b42318;
}
.history-title {
  font-size: 14px;
  margin: 0 0 8px;
}
</style>
