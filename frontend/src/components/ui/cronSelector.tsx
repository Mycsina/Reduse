import { Divider, Input } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import { Cron } from "react-js-cron";
import { useReducer } from "react";
import "react-js-cron/dist/styles.css";

interface CronState {
  inputValue: string;
  cronValue: string;
}

type CronAction =
  | { type: "set_input_value"; value: string }
  | { type: "set_cron_value"; value: string }
  | { type: "set_values"; value: string };

interface CronSelectorProps {
  value: string;
  onChange: (value: string) => void;
  defaultValue?: string;
}

function useCronReducer(initialValue: string) {
  const reducer = (state: CronState, action: CronAction): CronState => {
    switch (action.type) {
      case "set_input_value":
        return { ...state, inputValue: action.value };
      case "set_cron_value":
        return { ...state, cronValue: action.value, inputValue: action.value };
      case "set_values":
        return { cronValue: action.value, inputValue: action.value };
      default:
        return state;
    }
  };

  return useReducer(reducer, {
    inputValue: initialValue,
    cronValue: initialValue,
  });
}

export function CronSelector({
  value,
  onChange,
  defaultValue = "0 10 * * 1,3,5",
}: CronSelectorProps) {
  const [values, dispatchValues] = useCronReducer(value || defaultValue);

  const handleChange = (newValue: string) => {
    dispatchValues({
      type: "set_values",
      value: newValue,
    });
    onChange(newValue);
  };

  return (
    <div className="space-y-4">
      <Input
        value={values.inputValue}
        onChange={(event) => {
          dispatchValues({
            type: "set_input_value",
            value: event.target.value,
          });
        }}
        onBlur={() => {
          const newValue = values.inputValue;
          dispatchValues({
            type: "set_cron_value",
            value: newValue,
          });
          onChange(newValue);
        }}
        onPressEnter={() => {
          const newValue = values.inputValue;
          dispatchValues({
            type: "set_cron_value",
            value: newValue,
          });
          onChange(newValue);
        }}
      />
      <Divider>OR</Divider>
      <Cron value={values.cronValue} setValue={handleChange} />
    </div>
  );
}
