{{/* Backward-compatible collector mode for releases created before chart 1.1.0. */}}
{{- define "tinycars.collectorType" -}}
{{- $collector := .Values.collector | default dict -}}
{{- $configured := get $collector "type" -}}
{{- if $configured -}}
{{- $configured -}}
{{- else if contains "dynatrace" .Values.otel.endpoint -}}
dynatrace
{{- else -}}
bindplane
{{- end -}}
{{- end -}}
