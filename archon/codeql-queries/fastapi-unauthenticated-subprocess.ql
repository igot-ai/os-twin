/**
 * @name Unauthenticated FastAPI route executing subprocess
 * @description A FastAPI route handler that calls subprocess.run/Popen without
 *              a Depends(get_current_user) parameter, enabling unauthenticated
 *              OS command execution.
 * @kind problem
 * @problem.severity error
 * @id python/fastapi-unauth-subprocess
 * @tags security
 *       external/cwe/cwe-78
 *       external/cwe/cwe-306
 */

import python
import semmle.python.ApiGraphs

from Function handler, Call subprocessCall
where
  // The function is decorated with a FastAPI route decorator
  exists(Decorator d | d = handler.getADecorator() |
    d.getExpr().(Attribute).getName() in ["get", "post", "put", "patch", "delete"]
  ) and
  // The handler does NOT have a parameter with a Depends call as default
  not exists(Parameter p | p = handler.getArgByName(_) |
    p.getDefault().(Call).getFunc().(Name).getId() = "Depends"
  ) and
  // The handler calls subprocess.run, Popen, call, check_call, or check_output
  subprocessCall.getEnclosingFunction() = handler and
  exists(Attribute attr | attr = subprocessCall.getFunc() |
    attr.getName() in ["run", "Popen", "call", "check_call", "check_output"] and
    attr.getObject().(Name).getId() = "subprocess"
  )
select handler, "FastAPI route '" + handler.getName() + "' calls subprocess without authentication dependency (CWE-78, CWE-306)"
