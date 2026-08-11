variable "project_id" {
  type        = string
  description = "The GCP Project ID"
}

variable "region" {
  type        = string
  description = "The region to deploy resources to"
  default     = "us-central1"
}

variable "image_tag" {
  type        = string
  description = "The tag of the image to deploy"
  default     = "latest"
}

