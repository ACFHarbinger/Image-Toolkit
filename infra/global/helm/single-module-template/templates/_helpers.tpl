{{- define "single-module-template.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "single-module-template.labels" -}}
app: {{ include "single-module-template.name" . }}
{{- end -}}
