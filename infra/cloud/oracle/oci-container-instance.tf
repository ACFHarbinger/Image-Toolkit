# infra/cloud/oracle/oci-container-instance.tf
# Oracle Cloud Infrastructure (OCI) Terraform stack for the Image Toolkit
# heavy-request worker as a Container Instance (serverless containers; GPU
# shapes available for deep-learning generation).
#
# Apply:  terraform -chdir=infra/cloud/oracle init && terraform -chdir=infra/cloud/oracle apply

terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.0.0"
    }
  }
}

variable "tenancy_ocid" {}
variable "compartment_ocid" {}
variable "region" { default = "us-ashburn-1" }
variable "subnet_ocid" {}
variable "image_url" {
  description = "OCIR image, e.g. iad.ocir.io/<ns>/image-toolkit/worker:latest"
}

provider "oci" {
  tenancy_ocid = var.tenancy_ocid
  region       = var.region
}

resource "oci_container_instances_container_instance" "worker" {
  compartment_id = var.compartment_ocid
  display_name   = "image-toolkit-worker"
  # CI.Standard.E4.Flex for extraction; VM.GPU.A10 for generation jobs.
  shape = "CI.Standard.E4.Flex"
  shape_config {
    ocpus         = 4
    memory_in_gbs = 16
  }
  availability_domain = data.oci_identity_availability_domain.ad.name

  containers {
    display_name = "worker"
    image_url    = var.image_url
    environment_variables = {
      STAGE          = "dev"
      RESULTS_BUCKET = "image-toolkit-results"
      JOBS_STREAM    = "image-toolkit-jobs"
    }
  }

  vnics {
    subnet_id             = var.subnet_ocid
    is_public_ip_assigned = false
  }

  container_restart_policy = "ON_FAILURE"
}

data "oci_identity_availability_domain" "ad" {
  compartment_id = var.tenancy_ocid
  ad_number      = 1
}

output "container_instance_id" {
  value = oci_container_instances_container_instance.worker.id
}
