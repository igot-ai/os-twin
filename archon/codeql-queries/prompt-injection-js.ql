/**
 * @name User input reaches LLM prompt without sanitization (prompt injection)
 * @description Discord message content flows directly into a Gemini generateContent
 *              call, enabling prompt injection attacks.
 * @kind path-problem
 * @problem.severity error
 * @id js/prompt-injection
 * @tags security
 *       external/cwe/cwe-74
 */

import javascript
import DataFlow::PathGraph

/**
 * Discord message content as a taint source.
 */
class DiscordMessageSource extends DataFlow::Node {
  DiscordMessageSource() {
    // message.content in event handlers
    exists(PropRead pr |
      pr.getPropertyName() = "content" and
      this = DataFlow::valueNode(pr)
    )
  }
}

/**
 * Gemini generateContent call as a taint sink.
 */
class GeminiGenerateContentSink extends DataFlow::Node {
  GeminiGenerateContentSink() {
    exists(MethodCallExpr call |
      call.getMethodName() = "generateContent" and
      this = DataFlow::valueNode(call.getAnArgument())
    )
  }
}

class PromptInjectionConfig extends TaintTracking::Configuration {
  PromptInjectionConfig() { this = "PromptInjectionConfig" }

  override predicate isSource(DataFlow::Node source) {
    source instanceof DiscordMessageSource
  }

  override predicate isSink(DataFlow::Node sink) {
    sink instanceof GeminiGenerateContentSink
  }
}

from PromptInjectionConfig config, DataFlow::PathNode source, DataFlow::PathNode sink
where config.hasFlowPath(source, sink)
select sink.getNode(), source, sink,
  "Discord user input flows unsanitized into Gemini prompt (CWE-74 Prompt Injection)"
