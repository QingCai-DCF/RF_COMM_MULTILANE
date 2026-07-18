# RDC-001: reset_n_i asserts endpoint-wide and every domain uses reset_sync.
# No broad false path is applied here.  Asynchronous CLR pins are identified by
# the tool; functional deassertion is structurally synchronized in each domain.
