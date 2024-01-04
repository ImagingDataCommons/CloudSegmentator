with temp as (
  SELECT 
    service.description serviceDescription, 
    sku.description skuDescription, 
    #labels,
    workflowId.value workflowId, 
    wdlTaskId.value wdlTaskId, 
    submissionId.value submissionId, 
    system_labels, 
    usage_start_time, 
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
    --service.description in ('Compute Engine') and 
    workflowId is not null 
  order by 
    usage_start_time desc, 
    workflowId asc, 
    wdlTaskId
) 
select 
  submissionId, 
  workflowId, 
  wdlTaskId, 
  date(usage_start_time) date, 
  sum(cost) total 
from 
  temp 
group by 
  submissionId, 
  workflowId, 
  wdlTaskId, 
  date 
order by 
  date desc, 
  submissionId, 
  workflowId, 
  wdlTaskId
