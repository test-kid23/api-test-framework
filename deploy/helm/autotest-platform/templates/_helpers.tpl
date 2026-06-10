{{/*
AutoTest Platform · Helper templates
*/}}

{{/*
PostgreSQL service hostname
*/}}
{{- define "autotest-platform.postgresHost" -}}
{{- if .Values.postgres.enabled -}}
autotest-postgres
{{- else -}}
{{ .Values.postgres.external.host | default "postgres.external" }}
{{- end -}}
{{- end -}}

{{/*
Redis service hostname
*/}}
{{- define "autotest-platform.redisHost" -}}
{{- if .Values.redis.enabled -}}
autotest-redis
{{- else -}}
{{ .Values.redis.external.host | default "redis.external" }}
{{- end -}}
{{- end -}}
