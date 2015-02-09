/*
 * Copyright 2014-present Facebook, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 */

package com.example

import com.facebook.buck.junit.testdata.simple_spock.test.SimpleGroovyMain
import spock.lang.Specification
import spock.lang.Subject

class SimpleSpec extends Specification {

    @Subject
    SimpleGroovyMain sut = new SimpleGroovyMain();

    def 'a simple passing test'()
    {
        given:
        int i = 0;

        when:
        i++;

        then:
        i == 1
    }
}
