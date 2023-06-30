#!/usr/bin/env ruby

# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

require 'tzinfo'
require 'json'

print "Enter the timezone name (e.g., 'America/New_York'): "
#timezone_name = gets.chomp
#dst_transitions = get_dst_transitions(timezone_name)
timezone_name = 'America/Los_Angeles'

puts "DST transitions (UNIX time) for the next ten years in #{timezone_name}:"

timezone = TZInfo::Timezone.get(timezone_name)

now = DateTime.now

start_date = DateTime.new(now.year, 1, 1, 0, 0, 0, now.zone)
end_date = DateTime.new(now.year + 10, 1, 1, 0, 0, 0, now.zone)

dst_transitions = []

timezone.transitions_up_to(end_date).each do |transition|
  if transition.timestamp_value > start_date.to_time.to_i
    dst_transitions << { timestamp: transition.timestamp_value, offset: transition.offset.base_utc_offset + transition.offset.std_offset }
  end
end

output = {
  timezone: timezone_name,
  transitions: dst_transitions
}

puts JSON.pretty_generate(output)
