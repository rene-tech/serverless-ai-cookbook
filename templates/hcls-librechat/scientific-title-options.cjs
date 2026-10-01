// Title calls do not inherit the agent's reasoning settings upstream. Bound only
// the approved Nebius GLM title model; never change other providers or chat runs.
module.exports = function titleOptions(options, endpoint) {
  if (endpoint !== 'Nebius Token Factory' || options.model !== 'zai-org/GLM-5.3-Flash') {
    return options;
  }
  return { ...options, modelKwargs: { ...options.modelKwargs, reasoning_effort: 'low' } };
};
