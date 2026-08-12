{{- define "hybrid-image-editor.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "hybrid-image-editor.labels" -}}
app: {{ include "hybrid-image-editor.name" . }}
{{- end -}}
