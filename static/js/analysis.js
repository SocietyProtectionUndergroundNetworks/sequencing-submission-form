  ////// ############################################# /////////
  ////// ############ STEP 12 STARTS HERE ############ /////////
  ////// ############################################# /////////
  function disableForm_step_12_run_report(form) {
      form.find('fieldset').attr('disabled', 'disabled');
  }
  // Use delegated events so listeners work even if the table is updated
  $(document).on('submit', '.step_12_form_run_report', function(event) {
      event.preventDefault();
      var form = $(this);
      var formData = new FormData(this); // Automatically gets IDs, regions, and CSRF

      // Explicitly handle the debug checkbox to ensure '0' is sent if unchecked
      var debugValue = form.find('input[name="debug"]').is(':checked') ? '1' : '0';
      formData.set('debug', debugValue);

      form.find('input[type="submit"]').prop('disabled', true).val('Generating...');

      $.ajax({
          url: '/generate_lotus2_report',
          type: 'POST',
          data: formData,
          contentType: false,
          processData: false,
          success: function(response) {
              if (response.result == "1") {
                  window.location.reload();
              }
          },
          error: function(xhr) {
              form.find('input[type="submit"]').prop('disabled', false).val('Generate');
              $('#step_12_msg').html("<p class='text-danger'>Error: " + (xhr.responseJSON?.error || "Unknown error") + "</p>");
          }
      });
  });
  function disableForm_step_12_delete_report(form) {
      form.find('fieldset').attr('disabled', 'disabled');
  }
  $(document).on('submit', '.step_12_form_delete_report', function(event) {
      event.preventDefault();
      if (!confirm('Are you sure you want to delete this Lotus2 report?')) return;

      var formData = new FormData(this);
      $.ajax({
          url: '/delete_lotus2_report',
          type: 'POST',
          data: formData,
          contentType: false,
          processData: false,
          success: function(response) {
              if (response.result == "1") {
                  window.location.reload();
              }
          }
      });
  });

  ////// ############################################# /////////
  ////// ############ STEP 12 ENDS HERE ############## /////////
  ////// ############################################# /////////

  ////// ############################################# /////////
  ////// ############ STEP 13 STARTS HERE ############ /////////
  ////// ############################################# /////////
  function disableForm_step_13_run_report(form) {
      form.find('fieldset').attr('disabled', 'disabled');
  }
  $(document).on('submit', '.step_13_form_run_report', function(event) {
      event.preventDefault();
      var form = $(this);
      var formData = new FormData(this);

      var debugValue = form.find('input[name="debug"]').is(':checked') ? '1' : '0';
      formData.set('debug', debugValue);

      form.find('input[type="submit"]').prop('disabled', true).val('Generating...');

      $.ajax({
          url: '/generate_rscripts_report',
          type: 'POST',
          data: formData,
          contentType: false,
          processData: false,
          success: function(response) {
              if (response.result == "1") {
                  window.location.reload();
              }
          },
          error: function(xhr) {
              form.find('input[type="submit"]').prop('disabled', false).val('Generate');
              $('#step_13_msg').html("<p class='text-danger'>Error: " + (xhr.responseJSON?.error || "Unknown error") + "</p>");
          }
      });
  });

  function disableForm_step_13_delete_report(form) {
      form.find('fieldset').attr('disabled', 'disabled');
  }
  $(document).on('submit', '.step_13_form_delete_report', function(event) {
      event.preventDefault();
      if (!confirm('Are you sure you want to delete this R-script report?')) return;

      var formData = new FormData(this);
      $.ajax({
          url: '/delete_rscripts_report',
          type: 'POST',
          data: formData,
          contentType: false,
          processData: false,
          success: function(response) {
              if (response.result == "1") {
                  window.location.reload();
              }
          }
      });
  });

  ////// ############################################# /////////
  ////// ############ STEP 13 ENDS HERE ############## /////////
  ////// ############################################# /////////