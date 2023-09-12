#create or replace table `idc-external-025.terra.terraCostAnalysis`
# as
INSERT INTO `idc-external-025.terra.terraCostAnalysis` (
  with temp as (
    SELECT 
      service.description serviceDescription, 
      sku.description skuDescription, 
      #labels,
      workflowId.value workflowId, 
      wdlTaskId.value wdlTaskId, 
      submissionId.value submissionId, 
      system_labels, 
      date(usage_start_time) usage_start_time, 
      usage_end_time, 
      location.location, 
      location.region, 
      location.country, 
      export_time, 
      cost, 
      currency, 
      usage.amount_in_pricing_units, 
      usage.pricing_unit, 
    FROM 
      `idc-terra-explore-admin.terra_cost_exports.gcp_billing_export_v1_01E8DE_3FD7A1_F95FEE` 
      left join unnest(labels) workflowId on workflowId.key = 'cromwell-workflow-id' 
      left join unnest(labels) submissionId on submissionId.key = 'terra-submission-id' 
      left join unnest(labels) wdlTaskId on wdlTaskId.key = 'wdl-task-name' 
    where 
      DATE(_PARTITIONTIME) = DATE_SUB(
        CURRENT_DATE(), 
        INTERVAL 1 DAY
      ) 
      AND workflowId is not null 
    order by 
      usage_start_time desc, 
      workflowId asc, 
      wdlTaskId
  ) 
  select 
    submissionId, 
    skuDescription, 
    workflowId, 
    wdlTaskId, 
    usage_start_time, 
    sum(cost) total 
  from 
    temp 
  group by 
    submissionId, 
    skuDescription, 
    workflowId, 
    wdlTaskId, 
    usage_start_time 
  order by 
    usage_start_time desc, 
    submissionId, 
    workflowId, 
    wdlTaskId
)
