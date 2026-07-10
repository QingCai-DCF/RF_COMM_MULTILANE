#include "rf_transport_backend.h"

static int valid(const rf_transport_backend_t *backend) {
  return backend != NULL && backend->ops != NULL;
}

int rf_transport_open(rf_transport_backend_t *backend) {
  return valid(backend) && backend->ops->open != NULL
             ? backend->ops->open(backend)
             : RF_TRANSPORT_ERR_ARGUMENT;
}

int rf_transport_get_capabilities(
    rf_transport_backend_t *backend,
    rf_transport_capabilities_t *capabilities) {
  return valid(backend) && capabilities != NULL &&
                 backend->ops->get_capabilities != NULL
             ? backend->ops->get_capabilities(backend, capabilities)
             : RF_TRANSPORT_ERR_ARGUMENT;
}

int rf_transport_submit_fragment(rf_transport_backend_t *backend,
                                 const uint8_t *payload,
                                 size_t payload_size, uint32_t lane_mask,
                                 uint32_t *token_out) {
  return valid(backend) && payload != NULL && token_out != NULL &&
                 backend->ops->submit_fragment != NULL
             ? backend->ops->submit_fragment(backend, payload, payload_size,
                                             lane_mask, token_out)
             : RF_TRANSPORT_ERR_ARGUMENT;
}

int rf_transport_poll_fragment_result(
    rf_transport_backend_t *backend, uint32_t token, uint32_t max_polls,
    rf_transport_fragment_result_t *result) {
  return valid(backend) && result != NULL &&
                 backend->ops->poll_fragment_result != NULL
             ? backend->ops->poll_fragment_result(backend, token, max_polls,
                                                  result)
             : RF_TRANSPORT_ERR_ARGUMENT;
}

int rf_transport_read_fragment(rf_transport_backend_t *backend,
                               uint32_t token, uint8_t *payload,
                               size_t payload_capacity,
                               size_t *payload_size) {
  return valid(backend) && payload != NULL && payload_size != NULL &&
                 backend->ops->read_fragment != NULL
             ? backend->ops->read_fragment(backend, token, payload,
                                           payload_capacity, payload_size)
             : RF_TRANSPORT_ERR_ARGUMENT;
}

int rf_transport_abort(rf_transport_backend_t *backend) {
  return valid(backend) && backend->ops->abort != NULL
             ? backend->ops->abort(backend)
             : RF_TRANSPORT_ERR_ARGUMENT;
}

int rf_transport_close(rf_transport_backend_t *backend) {
  return valid(backend) && backend->ops->close != NULL
             ? backend->ops->close(backend)
             : RF_TRANSPORT_ERR_ARGUMENT;
}

int rf_transport_get_metrics(rf_transport_backend_t *backend,
                             rf_transport_metrics_t *metrics) {
  return valid(backend) && metrics != NULL &&
                 backend->ops->get_metrics != NULL
             ? backend->ops->get_metrics(backend, metrics)
             : RF_TRANSPORT_ERR_ARGUMENT;
}
